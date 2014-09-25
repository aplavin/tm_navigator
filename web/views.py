from flask import render_template
from flask.ext.classy import FlaskView, route
import traceback
import sys
from data import (get_topics_all, get_documents_all, get_words_all,
                  get_topics_info, get_docs_info, get_words_info,
                  d_by_slug, w_by_word,
                  get_doc_content)
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
    def search(self, query='*'):
        return self.render_template(
            base_ep='{name}s'.format(name=self.name),
            base_title='{name}s'.format(name=self.name.capitalize()),
            query=query,
            settings=self.search_settings,
            results_page=self.search_results(query)
        )


    @route('/{name}s/search_results/<query>', endpoint='{name}s:search_results')
    def search_results(self, query):
        pass


class TopicView(EntitiesView):
    ind_by_name = staticmethod(int)
    get_data = staticmethod(lambda t: {'topic': get_topics_info([t])[0]})
    name = 'topic'


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
        }
    ]

    @staticmethod
    def get_data(d):
        doc = get_docs_info([d])[0]
        data = get_doc_content(doc)
        data.update(doc=doc)
        return data


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
