from flask import request, session, redirect
from flask.ext.mako import render_template
import traceback
from app import app, db, restless
import models as m
import assessment_models as am
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg_dialect
import sqlalchemy_searchable as searchable
from itertools import groupby


@app.route('/')
def overview():
    return render_template(
        'overview.html',
        words=db.session.query(m.Term).join(m.Modality).filter(m.Modality.name == 'words').order_by(
            m.Term.count.desc()),
        docs=db.session.query(m.Document),
        topics=db.session.query(m.Topic).order_by(m.Topic.probability.desc()),
        topics_cnts=db.session.query(m.Topic.level, sa.func.count()).group_by(m.Topic.level).order_by(m.Topic.level))


@app.route('/document/<slug>')
def document(slug):
    # the document itself
    document = db.session.query(m.Document).filter_by(slug=slug).one()

    doctopics = db.session.query(m.DocumentTopic) \
        .filter(m.DocumentTopic.document_id == document.id) \
        .filter(m.DocumentTopic.probability > 0.01) \
        .cte('doctopics')

    topics_filtered = db.session.query(m.Topic) \
        .select_from(doctopics).join(m.Topic) \
        .cte('topics_filtered', recursive=True)
    topics_filtered = topics_filtered.union(
        db.session.query(m.Topic)
            .join(m.Topic.children)
            .join(topics_filtered, m.TopicEdge.child_id == topics_filtered.c.id)
    )

    ta = sa.orm.aliased(topics_filtered)
    topics = db.session.query(m.Topic).select_entity_from(topics_filtered) \
        .outerjoin(doctopics) \
        .outerjoin(m.Topic.children) \
        .outerjoin(ta, m.TopicEdge.child) \
        .options(sa.orm.contains_eager(m.Topic.children).
                 contains_eager(m.TopicEdge.child, alias=ta)) \
        .options(sa.orm.contains_eager(m.Topic.documents, alias=doctopics).noload(m.DocumentTopic.document)) \
        .order_by(m.Topic.level, doctopics.c.probability.desc())
    topics = topics.all()

    return render_template('document.html', document=document, root_topic=topics[0])


@app.route('/term/<modality>/<text>')
def term(modality, text):
    term = db.session.query(m.Term) \
        .join(m.Modality).filter(m.Modality.name == modality) \
        .filter(m.Term.text == text) \
        .options(sa.orm.lazyload('topics').joinedload('topic')) \
        .options(sa.orm.lazyload('documents').joinedload('document')) \
        .one()
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
        ]
    })


@app.route('/_search_results/', endpoint='search_results')
@app.route('/_search_results/<query>', endpoint='search_results')
def search_results(query=''):
    query = searchable.parse_search_query(query)

    present_as = request.args.get('present_as', '')

    if present_as.startswith('groupby:'):
        q = db.session.query(m.Term) \
            .join(m.Term.modality).filter(m.Modality.name == present_as[len('groupby:'):]) \
            .join(m.Term.documents).join(m.DocumentTerm.document) \
            .filter(True if not query else m.Document.search_vector.match(query)) \
            .group_by(m.Term) \
            .add_columns(sa.func.count()) \
            .order_by(sa.desc(sa.func.count())) \
            .options(sa.orm.noload(m.Term.modality))
        results = q[:]
    elif present_as == 'topics':
        if query:
            raise Exception('search query not supported in this mode')

        db.session.execute('set work_mem = "100MB"')  # ~30 MB used for sort in terms query

        topics = db.session.query(m.Topic) \
            .outerjoin(m.Topic.children) \
            .options(sa.orm.contains_eager(m.Topic.children)) \
            .all()

        limit = 10

        rn_docs = sa.func.row_number().over(partition_by=m.DocumentTopic.topic_id,
                                            order_by=m.DocumentTopic.probability.desc())
        db.session.query(m.Topic, m.DocumentTopic, rn_docs) \
            .outerjoin(m.Topic.documents) \
            .from_self(m.Topic) \
            .filter(rn_docs <= limit) \
            .order_by(m.Topic.id, m.DocumentTopic.probability.desc()) \
            .options(sa.orm.contains_eager(m.Topic.documents)) \
            .all()  # this fills Topic.documents for all topics

        rn_terms = sa.func.row_number().over(partition_by=(m.TopicTerm.topic_id, m.TopicTerm.modality_id),
                                             order_by=m.TopicTerm.probability.desc())
        db.session.query(m.Topic, m.TopicTerm, rn_terms) \
            .outerjoin(m.Topic.terms) \
            .from_self(m.Topic) \
            .filter(rn_terms <= limit) \
            .order_by(m.Topic.id, m.TopicTerm.modality_id, m.TopicTerm.probability.desc()) \
            .options(sa.orm.contains_eager(m.Topic.terms)) \
            .all()  # this fills Topic.terms for all topics

        results = topics[0]  # the root topic
    else:
        q = db.session.query(m.Document) \
            .filter(True if not query else m.Document.search_vector.match(query)) \
            .order_by(sa.desc(sa.func.ts_rank_cd(m.Document.search_vector, sa.func.to_tsquery('russian', query)))) \
            .add_columns(m.Document.highlight('title', query)) \
            .options(sa.orm.subqueryload('topics'))
        results = [doc
                   for doc, title_hl in q[:50]
                   if [setattr(doc, 'title_hl', title_hl)]]

    return render_template('search_results.html',
                           query=query, present_as=present_as,
                           results=results, results_cnt=q.count() if present_as != 'topics' else None)


@app.route('/_search_results_group/<int:modality_id>/<int:term_id>/<query>', endpoint='search_results_group')
@app.route('/_search_results_group/<int:modality_id>/<int:term_id>/', endpoint='search_results_group')
def search_results_group(modality_id, term_id, query=''):
    q = db.session.query(m.Document) \
        .join(m.Document.terms).filter_by(modality_id=modality_id, term_id=term_id) \
        .filter(True if not query else m.Document.search_vector.match(query)) \
        .order_by(sa.desc(sa.func.ts_rank_cd(m.Document.search_vector, sa.func.to_tsquery('russian', query)))) \
        .add_columns(m.Document.highlight('title', query)) \
        .options(sa.orm.subqueryload('topics'))
    results = [doc
               for doc, title_hl in q[:50]
               if [setattr(doc, 'title_hl', title_hl)]]
    return render_template('search_results_group.html', results=results, results_cnt=q.count())


@app.route('/login', methods=['GET'])
@app.route('/login', methods=['POST'])
def login():
    if request.method == 'GET':
        if 'username' in session:
            del session['username']
    elif request.method == 'POST':
        session['username'] = request.form['username']
    return redirect(request.referrer)


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
            'desc': getattr(error, 'message', ''),
            'tech_desc': traceback.format_exc(),
            'name': error.__class__.__name__,
        }

    return render_template('error.html', **params), error.code


from itertools import chain

for error in chain(range(400, 420), range(500, 506)):
    app.errorhandler(error)(error_handler)
# app.errorhandler(Exception)(error_handler)
