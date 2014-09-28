from flask import render_template, request
from flask.ext.classy import FlaskView, route
from collections import defaultdict
import traceback
import sys
from data import (get_topics_all, get_documents_all, get_words_all,
                  get_topics_info, get_docs_info, get_words_info,
                  d_by_slug, w_by_word,
                  get_doc_content,
                  TopicTuple, DocumentTuple, WordTuple)
from search import do_search, highlight, vector_data, vector_length
from whoosh import sorting
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
    search_settings = []


    @route('/{name}s/search_results/', endpoint='{name}s:search_results')
    @route('/{name}s/search_results/<query>', endpoint='{name}s:search_results')
    def search_results(self, query=''):
        res = do_search('docs',
                        query,
                        ['title', 'title_ngrams', 'authors', 'authors_ngrams'],
                        [sorting.FieldFacet('topics', allow_overlap=True)])

        gr_weights = defaultdict(float)
        for (gr_name, gr_nums), (_, hits) in zip(res['groups'], res['grouped']):
    #         print gr_name
            for (sortkey, value, d), hit in zip(gr_nums, hits):
                gr_weights[gr_name] += value

        topics = [TopicTuple(name, gr_weights[name] / len(res['results']), hits) for name, hits in res['grouped']]
        topics += [TopicTuple(name, 0, [])
                   for name in map(unicode, range(50))
                   if name not in gr_weights]

        return self.render_template(highlight=highlight,
                                    vector_data=lambda hit, field: vector_data(self.indexname, hit, field).starmap(TopicTuple),
                                    topics=topics,
                                    query=query,
                                    **res)


class DocumentView(EntitiesView):
    ind_by_name = staticmethod(d_by_slug)
    name = 'document'
    indexname = 'docs'
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

        res = do_search('docs', query, fields, groupby)
        return self.render_template(format=format,
                                    highlight=highlight,
                                    vector_data=lambda hit, field: vector_data('docs', hit, field).starmap(TopicTuple),
                                    **res)


class WordView(EntitiesView):
    ind_by_name = staticmethod(w_by_word)
    get_data = staticmethod(lambda w: {'word': get_words_info([w])[0]})
    name = 'word'


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
