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


@app.route('/search')
def search():
    pass


class EntitiesView(FlaskView):

    @classmethod
    def build_route_name(cls, method_name):
        if method_name == 'single':
            return cls.name
        elif method_name == 'index':
            return cls.name + 's'
        else:
            return cls.name + ":%s" % method_name


    @classmethod
    def render_template(cls, **kwargs):
        name = '%s/%s.html' % (cls.name, sys._getframe().f_back.f_code.co_name)
        return render_template(name, **kwargs)


    @route('/<int:ind>')
    @route('/<name>')
    def single(self, ind=None, name=None):
        if ind is None:
            ind = self.ind_by_name(name)
        data = self.get_data(ind)
        return self.render_template(**data)


class TopicView(EntitiesView):
    ind_by_name = staticmethod(int)
    get_data = staticmethod(lambda t: {'topic': get_topics_info([t])[0]})
    name = 'topic'


class DocumentView(EntitiesView):
    ind_by_name = staticmethod(d_by_slug)
    name = 'document'

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
