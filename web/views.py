from flask import render_template, request
from flask.ext.classy import FlaskView, route
import traceback
import sys
from itertools import starmap
from lazylist import LazyList
from data import (get_topics_all, get_documents_all, get_words_all,
                  get_topics_info, get_docs_info, get_words_info,
                  d_by_slug, w_by_word,
                  get_doc_content,
                  TopicTuple, DocumentTuple, WordTuple)
from search import do_search, highlight, vector_data, vector_length
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


    @classmethod
    def vector_data(cls, hit, field):
        return LazyList(starmap(cls.vector_mapf[field], vector_data(cls.indexname, hit, field)))


    @classmethod
    def vector_length(cls, hit, field):
        return vector_length(cls.indexname, hit, field)


    @route('/{name}s/search_results/', endpoint='{name}s:search_results')
    @route('/{name}s/search_results/<query>', endpoint='{name}s:search_results')
    def search_results(self, query=''):
        format = request.args.get('format', 'full')
        res = do_search(self.indexname, query, self.get_field(), self.get_groupby(), self.search_kwargs)
        return self.render_template(format=format, highlight=highlight, vector_data=self.vector_data, vector_length=self.vector_length, **res)


class TopicView(EntitiesView):
    ind_by_name = staticmethod(int)
    get_data = staticmethod(lambda t: {'topic': get_topics_info([t])[0]})
    name = 'topic'
    indexname = 'topics'
    search_settings = []
    get_field = staticmethod(lambda: ['doctitles', 'docauthors', 'words'])
    get_groupby = staticmethod(lambda: None)
    search_kwargs = {'sortedby': 'p', 'reverse': True}
    vector_mapf = {'words': WordTuple, 'docslugs': DocumentTuple, 'docauthors': WordTuple}


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


    @staticmethod
    def get_field():
        fields = ['title', 'authors', 'authors_ngrams', 'title_ngrams']
        if request.args.get('content_search', False) == 'true':
            fields.append('content')
        return fields


    @staticmethod
    def get_groupby():
        groupby = request.args.get('grouping')
        if not groupby:
            return None
        groupby = groupby.split(',')
        from whoosh import sorting
        return [sorting.FieldFacet(field, allow_overlap=True) if not field.endswith('_stored') else sorting.StoredFieldFacet(field[:-7])
                for field in groupby]


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
