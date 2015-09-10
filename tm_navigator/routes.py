import traceback
from main import mp, db
from flask import request, session, redirect
from models import *
from assessment_models import *
import sqlalchemy as sa
import sqlalchemy_searchable as searchable
from cached_property import cached_property


@mp.route('/browse/', to_url=lambda model: {'query': model.query})
@mp.template('browse.html')
class Browse:
    def __init__(self, query=''):
        self.query = query or request.args.get('query', '')
        self.settings =  [
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


@mp.route('/_search_results/', to_url=lambda model: {'query': model.query})
@mp.template('search_results.html')
class SearchResults:
    def __init__(self, query=''):
        self.query = query or request.args.get('query', '')
        self.present_as = request.args.get('present_as', '')

    @cached_property
    def query_parsed(self):
        return searchable.parse_search_query(self.query)

    @property
    def query_condition(self):
        return True if not self.query else Document.search_vector.match(self.query_parsed)

    @cached_property
    def results_cnt(self):
        if self.present_as.startswith('groupby:'):
            q = db.session.query(Term).join(Term.modality).filter(Modality.name == self.present_as[len('groupby:'):])
            return q.count()
        elif self.present_as == 'topics':
            if self.query_parsed:
                raise Exception('search query not supported in this mode')

            q = db.session.query(Topic)
            return q.count()
        else:
            q = db.session.query(Document).filter(self.query_condition)
            return q.count()

    @cached_property
    def results(self):
        if self.present_as.startswith('groupby:'):
            q = db.session.query(Term) \
                .join(Term.modality).filter(Modality.name == self.present_as[len('groupby:'):]) \
                .join(Term.documents).join(DocumentTerm.document) \
                .filter(self.query_condition) \
                .group_by(Term) \
                .add_columns(sa.func.count()) \
                .order_by(sa.desc(sa.func.count())) \
                .options(sa.orm.noload(Term.modality))
            return q[:]
        elif self.present_as == 'topics':
            if self.query_parsed:
                raise Exception('search query not supported in this mode')

            db.session.execute('set work_mem = "100MB"')  # ~30 MB used for sort in terms query

            topics = db.session.query(Topic) \
                .outerjoin(Topic.children) \
                .options(sa.orm.contains_eager(Topic.children)) \
                .all()

            limit = 10

            rn_docs = sa.func.row_number().over(partition_by=DocumentTopic.topic_id,
                                                order_by=DocumentTopic.probability.desc())
            topics_with_docs = db.session.query(Topic, DocumentTopic, rn_docs) \
                .outerjoin(Topic.documents) \
                .from_self(Topic) \
                .filter(rn_docs <= limit) \
                .order_by(Topic.id, DocumentTopic.probability.desc()) \
                .options(sa.orm.contains_eager(Topic.documents)) \
                .all()

            rn_terms = sa.func.row_number().over(partition_by=(TopicTerm.topic_id, TopicTerm.modality_id),
                                                 order_by=TopicTerm.probability.desc())
            topics_with_terms = db.session.query(Topic, TopicTerm, rn_terms) \
                .outerjoin(Topic.terms) \
                .from_self(Topic) \
                .filter(rn_terms <= limit) \
                .order_by(Topic.id, TopicTerm.modality_id, TopicTerm.probability.desc()) \
                .options(sa.orm.contains_eager(Topic.terms)) \
                .all()

            # XXX: without this there are queries executed for each topic and its terms and documents
            def _(t):
                for tt in t.children:
                    _(tt.child)
            _(topics[0])

            return topics[0]  # the root topic
        else:
            q = db.session.query(Document) \
                .filter(self.query_condition) \
                .order_by(sa.desc(sa.func.ts_rank_cd(Document.search_vector, sa.func.to_tsquery('russian', self.query_parsed)))) \
                .add_columns(Document.highlight('title', self.query_parsed)) \
                .options(sa.orm.subqueryload('topics'))
            return [doc
                    for doc, title_hl in q[:50]
                    if [setattr(doc, 'title_hl', title_hl)]]


@mp.route('/_search_results_group/<int:modality_id>/<int:term_id>/', to_url=lambda model: {'query': model.query})
@mp.template('search_results_group.html')
class SearchResultsGroup:
    def __init__(self, modality_id, term_id, query=''):
        self.modality_id = modality_id
        self.term_id = term_id
        self.query = query or request.args.get('query', '')
        self.present_as = None

    @cached_property
    def query_parsed(self):
        return searchable.parse_search_query(self.query)

    @property
    def query_condition(self):
        return True if not self.query else Document.search_vector.match(self.query_parsed)

    @cached_property
    def results_cnt(self):
        q = db.session.query(Document) \
            .join(Document.terms).filter_by(modality_id=self.modality_id, term_id=self.term_id) \
            .filter(self.query_condition)
        return q.count()

    @cached_property
    def results(self):
        q = db.session.query(Document) \
            .join(Document.terms).filter_by(modality_id=self.modality_id, term_id=self.term_id) \
            .filter(self.query_condition) \
            .order_by(sa.desc(sa.func.ts_rank_cd(Document.search_vector, sa.func.to_tsquery('russian', self.query_parsed)))) \
            .add_columns(Document.highlight('title', self.query_parsed)) \
            .options(sa.orm.subqueryload('topics'))
        return [doc
                for doc, title_hl in q[:50]
                if [setattr(doc, 'title_hl', title_hl)]]


@mp.route('/')
@mp.template('overview.html')
class Overview:
    @property
    def words(self):
        return db.session.query(Term)\
            .join(Modality).filter(Modality.name == 'words')\
            .order_by(Term.count.desc())\
            .options(sa.orm.contains_eager(Term.modality))

    def modality(self, name):
        return db.session.query(Modality).filter_by(name=name).one()

    @property
    def docs(self):
        return db.session.query(Document)

    @property
    def topics(self):
        return db.session.query(Topic).order_by(Topic.probability.desc())

    @property
    def topic_level_counts(self):
        return db.session.query(Topic.level, sa.func.count()).group_by(Topic.level).order_by(Topic.level)


@mp.route('/login/', methods=['POST'])
class Login:
    def __call__(self):
        session['username'] = request.form['username']
        return redirect(request.referrer)


@mp.route('/logout/')
class Logout:
    def __call__(self):
        if 'username' in session:
            del session['username']
        return redirect(request.referrer)


@mp.route('/document/<slug>/')
@mp.template('document.html')
@mp.ui_for(Document)
class UIDocument:
    def __init__(self, **values):
        self.document = db.session.query(Document).filter_by(**values).one()


    @property
    def root_topic(self):
        doctopics = db.session.query(DocumentTopic) \
            .filter(DocumentTopic.document_id == self.document.id) \
            .filter(DocumentTopic.probability > 0.01) \
            .cte('doctopics')
    
        topics_filtered = db.session.query(Topic) \
            .select_from(doctopics).join(Topic) \
            .cte('topics_filtered', recursive=True)
        topics_filtered = topics_filtered.union(
            db.session.query(Topic)
                .join(Topic.children)
                .join(topics_filtered, TopicEdge.child_id == topics_filtered.c.id)
        )
    
        ta = sa.orm.aliased(topics_filtered)
        topics = db.session.query(Topic).select_entity_from(topics_filtered) \
            .outerjoin(doctopics) \
            .outerjoin(Topic.children) \
            .outerjoin(ta, TopicEdge.child) \
            .options(sa.orm.contains_eager(Topic.children).
                     contains_eager(TopicEdge.child, alias=ta)) \
            .options(sa.orm.contains_eager(Topic.documents, alias=doctopics).noload(DocumentTopic.document)) \
            .order_by(Topic.level, doctopics.c.probability.desc())
        topics = topics.all()

        for t in topics:
            tt = db.session.query(Topic).filter_by(id=t.id)\
                .outerjoin(Topic.terms).order_by(TopicTerm.probability.desc()).limit(10)\
                .options(sa.orm.contains_eager(Topic.terms))\
                .one()
            sa.orm.attributes.set_committed_value(t, 'terms', tt.terms)
        
        return topics[0]


@mp.route('/term/<modality>/<text>/', to_url=lambda model: {'modality': model.modality.name})
@mp.template('term.html')
@mp.ui_for(Term)
class UITerm:
    def __init__(self, modality, text):
        self.term = db.session.query(Term).filter(Term.text == text)\
            .join(Modality).filter(Modality.name == modality)\
            .one()


@mp.route('/topic/<id>/')
@mp.template('topic.html')
@mp.ui_for(Topic)
class UITopic:
    def __init__(self, id):
        self.topic = db.session.query(Topic).filter_by(id=id)\
            .outerjoin(Topic.documents).order_by(DocumentTopic.probability.desc())\
            .options(sa.orm.contains_eager(Topic.documents))\
            .one()
        topic = db.session.query(Topic).filter_by(id=id)\
            .outerjoin(Topic.terms).order_by(TopicTerm.probability.desc()).limit(100)\
            .options(sa.orm.contains_eager(Topic.terms))\
            .one()
        sa.orm.attributes.set_committed_value(self.topic, 'terms', topic.terms)


@mp.route('/assess/<cls>/',
          to_url=lambda model: {
              'cls': model.__class__.__name__,
              **{local.name: getattr(model.src, remote.name)
                 for local, remote in model.__class__.src.property.local_remote_pairs},
              **{k: v
                 for k, v in model.__dict__.items()
                 if not k.startswith('_') and k != 'src'},
          },
          from_url={'cls': lambda cls: globals()[cls]},
          methods=['POST'])
@mp.ui_for(AssessmentMixin)
class UIAssessment:
    def __init__(self, cls):
        self.assessment = globals()[cls]()
        if 'username' in session:
            self.assessment.username = session['username']
        self.assessment.technical_info = {
            'user_agent': request.user_agent.string,
            'referrer': request.referrer,
            'access_route': request.access_route
        }
        for k, v in request.args.items():
            setattr(self.assessment, k, v)
        for k, v in request.form.items():
            setattr(self.assessment, k, v)

    def __call__(self):
        res = repr(self.assessment)
        db.session.add(self.assessment)
        db.session.commit()
        return res


@mp.errorhandler()
@mp.template('error.html')
class UIError:
    def __init__(self, error):
        self.error = error

    @property
    def code(self):
        return getattr(self.error, 'code', 500)

    @property
    def description(self):
        return getattr(self.error, 'description', getattr(self.error, 'message', ''))

    @property
    def name(self):
        return getattr(self.error, 'name', self.error.__class__.__name__)

    @property
    def technical_info(self):
        return traceback.format_exc()
