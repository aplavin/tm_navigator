from flask import render_template, request, jsonify
import traceback
from app import app, db
import models as m
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg_dialect
import sqlalchemy_searchable as searchable
from itertools import groupby


@app.route('/')
def overview():
    return render_template(
        'overview.html',
        words=db.session.query(m.Term).join(m.Modality).filter(m.Modality.name == 'words').order_by(m.Term.count.desc()),
        docs=db.session.query(m.Document).order_by(m.Document.length.desc()),
        topics=db.session.query(m.Topic).order_by(m.Topic.probability.desc()),
        topics_cnts=db.session.query(m.Topic.level, m.func.count()).group_by(m.Topic.level).order_by(m.Topic.level))


@app.route('/document/<path:name>')
def document(name):
    document = db.session.query(m.Document).filter_by(file_name=name).one()
    return render_template('document.html', document=document)


@app.route('/term/<modality>/<text>')
def term(modality, text):
    term = db.session.query(m.Term)\
        .join(m.Modality).filter(m.Modality.name == modality)\
        .filter(m.Term.text == text)\
        .one()\
        .options(sa.orm.lazyload('topics').joinedload('topic'))\
        .options(sa.orm.lazyload('documents').joinedload('document'))
    return render_template('term.html', term=term)


@app.route('/topic/<int:id>')
def topic(id):
    topic = db.session.query(m.Topic).filter_by(id=id).one()
    return render_template('topic.html', topic=topic)


@app.route('/browse/', endpoint='browse')
@app.route('/browse/<query>', endpoint='browse')
def browse(query=''):
    return render_template('browse.html', **{
        'query': query,
        'settings': [
            {
                'mode': 'choice',
                'name': 'present_as',
                'options': [
                    {'text': 'Plain list of documents', 'value': ''},
                    {'text': 'Documents grouped by author', 'value': 'groupby:authors'},
                    {'text': 'List of topics', 'value': 'topics'},
                ]
            }
        ],
        'results_page': search_results(query)
    })


@app.route('/_search_results/', endpoint='search_results')
@app.route('/_search_results/<query>', endpoint='search_results')
def search_results(query=''):
    query = searchable.parse_search_query(query)

    present_as = request.args.get('present_as', '')

    if present_as.startswith('groupby:'):
        q = db.session.query(m.Term)\
            .join(m.Term.modality).filter(m.Modality.name == present_as[len('groupby:'):])\
            .join(m.Term.documents).join(m.DocumentTerm.document)\
            .filter(True if not query else m.Document.search_vector.match(query))\
            .group_by(m.Term)\
            .add_columns(sa.func.count())\
            .order_by(sa.desc(sa.func.count()))
        results = q[:]
    elif present_as == 'topics':
        if query:
            raise Exception('search query not supported in this mode')

        rn_docs = sa.func.row_number().over(partition_by=m.DocumentTopic.topic_id,
                                            order_by=m.DocumentTopic.probability.desc())
        q_docs = db.session.query(m.Topic, m.DocumentTopic, m.Document, rn_docs)\
            .join(m.Topic.documents).join(m.DocumentTopic.document)\
            .filter(True if not query else m.Document.search_vector.match(query))\
            .from_self(m.Topic)\
            .filter(rn_docs <= 50)\
            .order_by(m.DocumentTopic.topic_id, m.DocumentTopic.probability.desc())\
            .options(sa.orm.contains_eager('documents').contains_eager('document'))

        rn_terms = sa.func.row_number().over(partition_by=m.TopicTerm.topic_id,
                                             order_by=m.TopicTerm.probability.desc())
        q_terms = db.session.query(m.TopicTerm, m.Modality, rn_terms)\
            .join(m.TopicTerm.modality).filter(m.Modality.name == 'words')\
            .from_self(m.TopicTerm)\
            .filter(rn_terms <= 50)\
            .join(m.TopicTerm.term)\
            .order_by(m.TopicTerm.topic_id, m.TopicTerm.probability.desc())\
            .options(sa.orm.contains_eager('term'))\
            .options(sa.orm.lazyload('modality'))\
            .options(sa.orm.lazyload('topic'))

        topics = q_docs.all()
        q = q_docs

        t_terms = {topic_id: list(xs)
                   for topic_id, xs in groupby(q_terms, lambda x: x.topic_id)}
        for t in topics:
            sa.orm.attributes.set_committed_value(t, 'terms', t_terms.get(t.id, []))

        results = topics

        q_hierarchy = db.session.query(m.Topic)\
            .filter(m.Topic.level == 0)\
            .options(sa.orm.joinedload_all(*['children', 'child']*5))
        results = (results, q_hierarchy.one())
    else:
        q = db.session.query(m.Document)\
            .filter(True if not query else m.Document.search_vector.match(query))\
            .order_by(sa.desc(sa.func.ts_rank_cd(m.Document.search_vector, sa.func.to_tsquery('russian', query))))\
            .add_columns(m.Document.highlight('title', query))\
            .options(sa.orm.subqueryload('topics'))
        results = [doc
                   for doc, title_hl in q[:50]
                   if [setattr(doc, 'title_hl', title_hl)]]

    return render_template('search_results.html',
                           query=query, present_as=present_as,
                           results=results, results_cnt=q.count())


@app.route('/_search_results_group/<int:modality_id>/<int:term_id>/<query>', endpoint='search_results_group')
@app.route('/_search_results_group/<int:modality_id>/<int:term_id>/', endpoint='search_results_group')
def search_results_group(modality_id, term_id, query=''):
    q = db.session.query(m.Document)\
        .join(m.Document.terms).filter_by(modality_id=modality_id, term_id=term_id)\
        .filter(True if not query else m.Document.search_vector.match(query))\
        .order_by(sa.desc(sa.func.ts_rank_cd(m.Document.search_vector, sa.func.to_tsquery('russian', query))))\
        .add_columns(m.Document.highlight('title', query))\
        .options(sa.orm.subqueryload('topics'))
    results = [doc
               for doc, title_hl in q[:50]
               if [setattr(doc, 'title_hl', title_hl)]]
    return render_template('search_results_group.html', results=results, results_cnt=q.count())


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

from itertools import chain

for error in chain(range(400, 420), range(500, 506)):
    app.errorhandler(error)(error_handler)
# app.errorhandler(Exception)(error_handler)
