from flask import render_template
import traceback
from data import (get_topics_all, get_documents_all, get_words_all,
                  get_topics_info, get_docs_info, get_words_info,
                  d_by_slug, w_by_word,
                  get_doc_content)
from app import app


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


@app.route('/topic/<int:t>')
def topic(t):
    topic = get_topics_info([t])[0]
    return render_template('topic/single.html', topic=topic)


@app.route('/document/<slug>')
@app.route('/document/<int:d>')
@app.route('/document/<int:d>/<slug>')
def document(slug=None, d=None):
    if d is None:
        d = d_by_slug(slug)

    doc = get_docs_info([d])[0]
    data = get_doc_content(doc)

    return render_template('document/single.html',
                            doc=doc,
                            topics_flow=data['topics_flow'],
                            html_content=data['html'],
                            topics_in_content=data['topics_in_content'])


@app.route('/word/w/<int:w>')
@app.route('/word/<word>')
def word(w=None, word=None):
    word = get_words_info([w if w is not None else w_by_word(word)])[0]
    return render_template('word/single.html', word=word)
