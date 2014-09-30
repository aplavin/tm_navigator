from flask import render_template, request
from flask.ext.classy import FlaskView, route
from collections import defaultdict
import traceback
import sys
from data import (get_topics_all, get_documents_all, get_words_all,
                  get_topics_info, get_docs_info, get_words_info,
                  d_by_slug, w_by_word,
                  get_doc_content,
                  TopicTuple, DocumentTuple, WordTuple,
                  get as data_get)
from search import do_search, highlight, vector_data
from whoosh import sorting
import numpy as np
from app import app


@app.route('/')
def overview():
    return render_template(
        'overview.html',
        words=get_words_all(),
        docs=get_documents_all(),
        topics=get_topics_all())


class EntitiesView(FlaskView):
    route_base = ''

    @classmethod
    def postprocess_endpoint(cls, endpoint):
        return endpoint.format(name=cls.name)


    @classmethod
    def build_rule(cls, rule, method=None):
        return rule.format(name=cls.name)


    @classmethod
    def render_template(cls, **kwargs):
        name = '%s/%s.html' % (cls.name, sys._getframe().f_back.f_code.co_name)
        return render_template(name, **kwargs)


    @route('/{name}/<int:ind>', endpoint='{name}')
    @route('/{name}/<name>', endpoint='{name}')
    def single(self, ind=None, name=None):
        if ind is None:
            ind = self.ind_by_name(name)
        data = self.get_data(ind)
        return self.render_template(**data)


    @route('/{name}s/', endpoint='{name}s')
    def index(self):
        return self.search()


    @route('/{name}s/search/', endpoint='{name}s:search')
    @route('/{name}s/search/<query>', endpoint='{name}s:search')
    def search(self, query=''):
        return self.render_template(
            base_ep='{name}s'.format(name=self.name),
            base_title='{name}s'.format(name=self.name.capitalize()),
            query=query,
            settings=self.search_settings,
            results_page=self.search_results(query)
        )


class TopicView(EntitiesView):
    ind_by_name = staticmethod(int)
    get_data = staticmethod(lambda t: {'topic': get_topics_info([t])[0]})
    name = 'topic'
    search_settings = [
        {
            'mode': 'bool',
            'name': 'content_search',
            'text': 'In-text search'
        },
        {
            'mode': 'bool',
            'name': 'words_search',
            'text': 'Search for words also'
        }
    ]


    @route('/{name}s/search_results/', endpoint='{name}s:search_results')
    @route('/{name}s/search_results/<query>', endpoint='{name}s:search_results')
    def search_results(self, query=''):
        fields = ['title', 'authors', 'authors_ngrams', 'title_ngrams']
        if request.args.get('content_search', False) == 'true':
            fields.append('content')

        res = do_search('docs',
                        query,
                        fields,
                        [sorting.FieldFacet('topics', allow_overlap=True)])

        gr_weights = defaultdict(float)
        for (gr_name, gr_nums), (_, hits) in zip(res['groups'], res['grouped']):
            for (sortkey, value, d), hit in zip(gr_nums, hits):
                if not hasattr(hit, 'gr_weights'):
                    hit.gr_weights = {}
                hit.gr_weights[gr_name] = value
                gr_weights[gr_name] += value

        topics = [TopicTuple(name, gr_weights[name] / len(res['results']), sorted(hits, key=lambda h: h.gr_weights[name], reverse=True))
                  for name, hits in res['grouped']]

        def _highlight(hit, hl_name, fields, fallback=None):
            if query and _highlight.cnt < 200:
                _highlight.cnt += 1
                return highlight(hit, hl_name, fields, fallback)
            else:
                return hit[fallback]
        _highlight.cnt = 0

        if query and request.args.get('words_search', False) == 'true':
            words_res = do_search('words',
                                  query,
                                  ['word', 'word_ngrams'],
                                  None,
                                  kwargs={'limit': None})
            ws_matched = np.array(sorted(hit.docnum
                                         for hit in words_res['results']))
            highlights = {hit.docnum: _highlight(hit, 'whole', ['word', 'word_ngrams'])
                          for hit in words_res['results']}

            if len(ws_matched) > 0:
                ptw_matched = data_get('p_wt')[ws_matched].T
                ts_matched = ptw_matched.sum(1).argsort()[::-1]

                new_topics = []
                for t, pw in zip(ts_matched, ptw_matched[ts_matched]):
                    ws = pw.argsort()[::-1]
                    pw = pw[ws]
                    ws = ws_matched[ws]

                    words = [WordTuple(w, p, highlights[w]) for w, p in zip(ws, pw)]
                    words = filter(lambda w: w.np > 0, words)
                    if pw.sum() > 0:
                        new_topics.append(TopicTuple(t, pw.sum(), None, words))

                ts = [t.t for t in topics]
                ts += [unicode(t.t) for t in new_topics if unicode(t.t) not in ts]

                topics = defaultdict(TopicTuple, {t.t: t for t in topics})
                new_topics = defaultdict(TopicTuple, {unicode(t.t): t for t in new_topics})
                topics = [TopicTuple(t, (topics[t].np or 0, new_topics[t].np or 0), topics[t].documents or [], new_topics[t].words or [])
                          for t in ts]
            else:
                topics = [TopicTuple(t.t, (t.np, 0), t.documents, [])
                          for t in topics]
        else:
            topics_info = get_topics_info([t.t for t in topics], ntop=(0, -1))
            topics = [TopicTuple(t.t, (t.np, 0), t.documents, topics_info[i].words)
                      for i, t in enumerate(topics)]

        res['results_cnt'] = len(topics)

        return self.render_template(highlight=_highlight,
                                    topics=topics,
                                    query=query,
                                    **res)


class DocumentView(EntitiesView):
    ind_by_name = staticmethod(d_by_slug)
    name = 'document'
    search_settings = [
        {
            'mode': 'choice',
            'name': 'grouping',
            'options': [
                {'text': 'Disable grouping', 'value': ''},
                {'text': '-'},
                {'text': 'Group by authors', 'value': 'authors_tags_stored'},
                {'text': 'Group by individual author', 'value': 'authors_tags'},
                {'text': 'Group by source', 'value': 'conference,year'},
            ]
        },
        {
            'mode': 'bool',
            'name': 'content_search',
            'text': 'In-text search'
        },
        {
            'mode': 'choice',
            'name': 'format',
            'options': [
                {'text': 'Full format', 'value': ''},
                {'text': 'Short format', 'value': 'short'},
                {'text': 'Shortest format', 'value': 'shortest'},
            ]
        }
    ]
    vector_mapf = {'topics': TopicTuple}
    search_kwargs = {}


    @staticmethod
    def get_data(d):
        doc = get_docs_info([d])[0]
        data = get_doc_content(doc)
        data.update(doc=doc)
        return data


    @route('/{name}s/search_results/', endpoint='{name}s:search_results')
    @route('/{name}s/search_results/<query>', endpoint='{name}s:search_results')
    def search_results(self, query=''):
        format = request.args.get('format', 'full')

        fields = ['title', 'authors', 'authors_ngrams', 'title_ngrams']
        if request.args.get('content_search', False) == 'true':
            fields.append('content')

        groupby = request.args.get('grouping')
        if not groupby:
            groupby = None
        else:
            groupby = groupby.split(',')
            groupby = [sorting.FieldFacet(field, allow_overlap=True) if not field.endswith('_stored') else sorting.StoredFieldFacet(field[:-7])
                       for field in groupby]

        def hcontent(hit):
            import codecs, re
            with codecs.open('static/docsdata/%s.html' % hit['fname'], encoding='utf-8') as f:
                html = f.read()
                m = re.search(r'</header>(.*)</body>', html, re.DOTALL)
                html = m.group(1)
                content = re.sub('<[^<]+?>', ' ', html)
            return highlight(hit, 'pinpoint', ['content'], text=content)

        res = do_search('docs', query, fields, groupby)
        return self.render_template(format=format,
                                    highlight=highlight,
                                    hcontent=hcontent,
                                    vector_data=lambda hit, field: vector_data('docs', hit, field).starmap(TopicTuple),
                                    **res)


class WordView(EntitiesView):
    ind_by_name = staticmethod(w_by_word)
    get_data = staticmethod(lambda w: {'word': get_words_info([w])[0]})
    name = 'word'
    search_settings = []


    @route('/{name}s/search_results/', endpoint='{name}s:search_results')
    @route('/{name}s/search_results/<query>', endpoint='{name}s:search_results')
    def search_results(self, query=''):
        res = do_search('words', query, ['word', 'word_ngrams'], None, {'sortedby': 'n', 'reverse': True})
        words = [WordTuple(hit['word'], hit['n'], highlight(hit, 'whole', ['word', 'word_ngrams'], 'word'))
                 for hit in res['results']]

        ws = [hit['w'] for hit in res['results']]
        word_infos = get_words_info(ws, ntop=(-1, -1))

        words = [WordTuple(w.w, w.np, w.word, wi.topics, wi.documents)
                 for w, wi in zip(words, word_infos)]

        return self.render_template(format=format,
                                    highlight=highlight,
                                    words=words,
                                    **res)


TopicView.register(app)
DocumentView.register(app)
WordView.register(app)


def error_handler(error):
    if hasattr(error, 'code'):
        params = {
            'code': error.code,
            'desc': error.description,
            'name': error.name,
        }
    else:
        error.code = 500
        params = {
            'code': error.code,
            'desc': error.message,
            'tech_desc': traceback.format_exc(),
            'name': error.__class__.__name__,
        }

    return render_template('error.html', **params), error.code


for error in range(400, 420) + range(500, 506):
    app.errorhandler(error)(error_handler)
# app.errorhandler(Exception)(error_handler)
