from flask import request, session, redirect
from flask.ext.mako import render_template
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
        words=db.session.query(m.Term).join(m.Modality).filter(m.Modality.name == 'words').order_by(
            m.Term.count.desc()),
        docs=db.session.query(m.Document),
        topics=db.session.query(m.Topic).order_by(m.Topic.probability.desc()),
        topics_cnts=db.session.query(m.Topic.level, m.func.count()).group_by(m.Topic.level).order_by(m.Topic.level))


@app.route('/document/<slug>')
def document(slug):
    # the document itself
    document = db.session.query(m.Document).filter_by(slug=slug).one()

    # topics hierarchy, including only those with non-zero probability in this document and their parents
    doctopics = db.session.query(m.DocumentTopic).filter_by(document_id=document.id).cte('doctopics')

    all_child_probs = db.session.query(doctopics.c.topic_id.label('id'),
                                       doctopics.c.probability) \
        .cte('all_child_probs', recursive=True)
    all_child_probs = all_child_probs.union_all(
        db.session.query(m.Topic.id,
                         all_child_probs.c.probability)
            .join(m.Topic.children)
            .join(all_child_probs, m.TopicEdge.child_id == all_child_probs.c.id)
    )

    max_subtree_probs = db.session.query(m.Topic) \
        .join(all_child_probs) \
        .group_by(m.Topic) \
        .having(sa.func.max(all_child_probs.c.probability) > 0.01) \
        .cte('max_subtree_probs')

    # start building eager load options
    q_options = sa.orm
    q_o = []

    # store all aliases for convenience
    t_a = [sa.orm.aliased(m.Topic, max_subtree_probs.alias())]
    te_a = []
    dt_a = []

    # start with the topic #0
    hierarchy_q = db.session.query(t_a[-1]).filter(t_a[-1].level == 0)

    max_level = db.session.query(sa.func.max(m.Topic.level)).scalar()
    for _ in range(max_level):
        te_a.append(sa.orm.aliased(m.TopicEdge))
        t_a.append(sa.orm.aliased(m.Topic, max_subtree_probs.alias()))
        dt_a.append(sa.orm.aliased(m.DocumentTopic, doctopics.alias()))

        hierarchy_q = hierarchy_q \
            .outerjoin(te_a[-1], t_a[-2].children).outerjoin(t_a[-1], te_a[-1].child) \
            .outerjoin(dt_a[-1], t_a[-1].documents) \
            .order_by(t_a[-1].level, dt_a[-1].probability.desc())

        q_options = q_options.contains_eager('children', alias=te_a[-1]).contains_eager('child', alias=t_a[-1])
        q_o.append(q_options.contains_eager('documents', alias=dt_a[-1]).lazyload('document'))

    hierarchy_q = hierarchy_q.options(q_options.noload('children')).options(*q_o)
    root_topic = hierarchy_q.one()

    return render_template('document.html', document=document, root_topic=root_topic)


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
            .order_by(sa.desc(sa.func.count()))
        results = q[:]
    elif present_as == 'topics':
        if query:
            raise Exception('search query not supported in this mode')

        rn_docs = sa.func.row_number().over(partition_by=m.DocumentTopic.topic_id,
                                            order_by=m.DocumentTopic.probability.desc())
        q_docs = db.session.query(m.Topic, m.DocumentTopic, m.Document, rn_docs) \
            .join(m.Topic.documents).join(m.DocumentTopic.document) \
            .filter(True if not query else m.Document.search_vector.match(query)) \
            .from_self(m.Topic) \
            .filter(rn_docs <= 50) \
            .order_by(m.DocumentTopic.topic_id, m.DocumentTopic.probability.desc()) \
            .options(sa.orm.contains_eager('documents').contains_eager('document'))

        rn_terms = sa.func.row_number().over(partition_by=m.TopicTerm.topic_id,
                                             order_by=m.TopicTerm.probability.desc())
        q_terms = db.session.query(m.TopicTerm, m.Modality, rn_terms) \
            .join(m.TopicTerm.modality).filter(m.Modality.name == 'words') \
            .from_self(m.TopicTerm) \
            .filter(rn_terms <= 50) \
            .join(m.TopicTerm.term) \
            .order_by(m.TopicTerm.topic_id, m.TopicTerm.probability.desc()) \
            .options(sa.orm.contains_eager('term')) \
            .options(sa.orm.lazyload('modality')) \
            .options(sa.orm.lazyload('topic'))

        topics = q_docs.all()
        q = q_docs

        t_terms = {topic_id: list(xs)
                   for topic_id, xs in groupby(q_terms, lambda x: x.topic_id)}
        for t in topics:
            sa.orm.attributes.set_committed_value(t, 'terms', t_terms.get(t.id, []))

        results = topics

        q_hierarchy = db.session.query(m.Topic) \
            .filter(m.Topic.level == 0) \
            .options(sa.orm.joinedload_all(*['children', 'child'] * 5))
        results = (results, q_hierarchy.one())
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
                           results=results, results_cnt=q.count())


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
            'desc': error.message,
            'tech_desc': traceback.format_exc(),
            'name': error.__class__.__name__,
        }

    return render_template('error.html', **params), error.code


from itertools import chain

for error in chain(range(400, 420), range(500, 506)):
    app.errorhandler(error)(error_handler)
# app.errorhandler(Exception)(error_handler)
