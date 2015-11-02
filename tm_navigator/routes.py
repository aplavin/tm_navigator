import traceback
import re
from main import mp, db
from flask import request, session, redirect
from models import *
import sqlalchemy as sa
import sqlalchemy_searchable as searchable
from cached_property import cached_property


def add_modality_relationships(model, target, rel_name, rel_expr, order_by=None):
    for mod_id, mod_name in ((1, 'words'), (2, 'authors')):
        setattr(
            model,
            '%s_%s' % (rel_name, mod_name),
            sa.orm.relationship(
                target,
                primaryjoin=sa.and_(rel_expr,
                                    target.modality_id == mod_id),
                order_by=order_by
            )
        )


# add_modality_relationships(Document, Document.terms, DocumentTerm)
# add_modality_relationships(Topic, Topic.terms, TopicTerm)
add_modality_relationships(
    Document, DocumentTerm,
    'terms', Document.id == DocumentTerm.document_id, DocumentTerm.count.desc()
)
add_modality_relationships(
    Topic, TopicTerm,
    'terms', Topic.id == TopicTerm.topic_id
)


@mp.template('tms_list.html')
class TmsList:
    @property
    def datasets(self):
        return db.session.query(DatasetMeta).all()

    @property
    def topicmodels(self):
        return db.session.query(TopicModelMeta).all()

    @property
    def base_domain(self):
        return request.host


@mp.app.before_request
def set_schema():
    if request.endpoint == 'static':
        return

    try:
        domain = sa.bindparam('domain', request.host)
        tm = db.session.query(TopicModelMeta) \
            .filter(TopicModelMeta.domains.any(domain.startswith(TopicModelDomain.domain))) \
            .one()
        tm.activate_schemas()
    except sa.orm.exc.NoResultFound:
        SchemaMixin.activate_public_schema(db.session)
        return mp.get_view(TmsList())


@mp.route('/browse/')
@mp.template('browse.html')
class Browse:
    def __init__(self, query=''):
        self.query = query
        self.settings = [
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

    @classmethod
    def from_url(cls):
        query = request.args.get('query', '')
        return cls(query)

    def to_url(self):
        return {'query': self.query}


@mp.route('/_search_results/')
@mp.template('search_results.html')
class SearchResults:
    def __init__(self, query='', present_as=''):
        self.query = query
        self.present_as = present_as

    @classmethod
    def from_url(cls):
        query = request.args.get('query', '')
        present_as = request.args.get('present_as', '')
        return cls(query, present_as)

    def to_url(self):
        return {'query': self.query}

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
                                                order_by=DocumentTopic.prob_td.desc())
            topics_with_docs = db.session.query(Topic, DocumentTopic, rn_docs) \
                .outerjoin(Topic.documents) \
                .from_self(Topic) \
                .filter(rn_docs <= limit) \
                .order_by(Topic.id, DocumentTopic.prob_td.desc()) \
                .options(sa.orm.contains_eager(Topic.documents)
                         .joinedload(DocumentTopic.document)
                         .joinedload(Document.terms_authors)) \
                .all()

            rn_terms = sa.func.row_number().over(partition_by=(TopicTerm.topic_id, TopicTerm.modality_id),
                                                 order_by=TopicTerm.prob_wt.desc())
            topics_with_terms = db.session.query(Topic, TopicTerm, rn_terms) \
                .outerjoin(Topic.terms) \
                .from_self(Topic) \
                .filter(rn_terms <= limit) \
                .order_by(Topic.id, TopicTerm.modality_id, TopicTerm.prob_wt.desc()) \
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
                .order_by(sa.desc(sa.func.ts_rank_cd(Document.search_vector,
                                                     sa.func.to_tsquery('russian', self.query_parsed)))) \
                .add_columns(Document.highlight('title', self.query_parsed)) \
                .options(sa.orm.subqueryload('topics'))
            return [doc
                    for doc, title_hl in q[:50]
                    if [setattr(doc, 'title_hl', title_hl)]]


@mp.route('/_search_results_group/<int:modality_id>/<int:term_id>/')
@mp.template('search_results_group.html')
class SearchResultsGroup:
    def __init__(self, term, query):
        self.term = term
        self.query = query
        self.present_as = None  # used in template

    @classmethod
    def from_url(cls, modality_id, term_id, query=''):
        term = db.session.query(Term).filter_by(modality_id=modality_id, id=term_id).one()
        query = query or request.args.get('query', '')
        return cls(term, query)

    def to_url(self):
        return {'query': self.query, 'modality_id': self.term.modality_id, 'term_id': self.term.id}

    @cached_property
    def query_parsed(self):
        return searchable.parse_search_query(self.query)

    @property
    def query_condition(self):
        return True if not self.query else Document.search_vector.match(self.query_parsed)

    @cached_property
    def results_cnt(self):
        # TODO: filter by term itself
        q = db.session.query(Document) \
            .join(Document.terms).filter_by(modality_id=self.term.modality_id, term_id=self.term.id) \
            .filter(self.query_condition)
        return q.count()

    @cached_property
    def results(self):
        # TODO: filter by term itself
        q = db.session.query(Document) \
            .join(Document.terms).filter_by(modality_id=self.term.modality_id, term_id=self.term.id) \
            .filter(self.query_condition) \
            .order_by(sa.desc(sa.func.ts_rank_cd(Document.search_vector,
                                                 sa.func.to_tsquery('russian', self.query_parsed)))) \
            .add_columns(Document.highlight('title', self.query_parsed)) \
            .options(sa.orm.subqueryload('topics'),
                     sa.orm.joinedload(Document.terms_authors))
        return [doc
                for doc, title_hl in q[:50]
                if [setattr(doc, 'title_hl', title_hl)]]


@mp.route('/')
@mp.template('overview.html')
class Overview:
    @property
    def words(self):
        return db.session.query(Term) \
            .join(Modality).filter(Modality.name == 'words') \
            .order_by(Term.count.desc()) \
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


def load_hierarchy(filtered_seed):
    filtered_topics = db.session.query(Topic) \
        .select_from(filtered_seed).join(Topic) \
        .cte('filtered_topics', recursive=True)
    filtered_topics = filtered_topics.union(
        db.session.query(Topic)
            .join(Topic.children)
            .join(filtered_topics, TopicEdge.child)
    )

    ft_a = sa.orm.aliased(filtered_topics)
    topics = db.session.query(Topic).select_entity_from(filtered_topics) \
        .outerjoin(Topic.children) \
        .outerjoin(ft_a, TopicEdge.child) \
        .options(sa.orm.contains_eager(Topic.children).contains_eager(TopicEdge.child, alias=ft_a))
    topics = {t.id: t for t in topics}

    rn_terms = sa.func.row_number().over(partition_by=(TopicTerm.topic_id, TopicTerm.modality_id),
                                         order_by=TopicTerm.prob_wt.desc())
    topics_with_terms = db.session.query(Topic, TopicTerm, rn_terms) \
        .outerjoin(Topic.terms) \
        .join(filtered_topics, Topic.id == filtered_topics.c.id) \
        .from_self(Topic) \
        .filter(rn_terms <= 15) \
        .order_by(Topic.id, TopicTerm.modality_id, TopicTerm.prob_wt.desc()) \
        .options(sa.orm.contains_eager(Topic.terms))
    topics_with_terms.all()

    return topics


@mp.route('/document/<slug>/')
@mp.template('document.html')
@mp.ui_for(Document)
class _:
    @classmethod
    def from_url(cls, slug):
        document = db.session.query(Document).filter_by(slug=slug) \
            .options(sa.orm.joinedload(Document.contents, DocumentContent.topics)) \
            .one()
        return cls(document)

    @property
    def root_topic(self):
        doctopics = db.session.query(DocumentTopic) \
            .filter(DocumentTopic.document_id == self.model.id) \
            .filter(DocumentTopic.prob_td > 0.001) \
            .cte('doctopics')

        topics = load_hierarchy(doctopics)
        db.session.query(Topic).outerjoin(doctopics) \
            .options(sa.orm.contains_eager(Topic.documents, alias=doctopics).noload(DocumentTopic.document)) \
            .all()

        return topics[0]

    @property
    def html(self):
        html = self.model.html or ''

        html_new = ''
        html_pos = 0
        for cnt in self.model.contents:
            html_new += html[html_pos:cnt.start_pos]
            if cnt.topics:
                html_new += '<span data-word="%d" data-color="%d"><a href="#">' % (cnt.term_id, cnt.topics[0].topic_id)
            else:
                html_new += '<span data-word="%d"><a href="#">' % cnt.term_id
            html_new += html[cnt.start_pos:cnt.end_pos]
            html_new += '</a></span>'
            html_pos = cnt.end_pos
        html_new += html[html_pos:]

        try:
            html = re.search(r'</header>(.*)</body>', html_new, re.DOTALL).group(1)
            html = re.sub(r'<img class="(\w+)" src="\w+/(eqn\d+).png".*?/>',
                          r'<span class="sprite-\2"></span>',
                          html, flags=re.DOTALL | re.MULTILINE)
        except AttributeError:
            pass

        return html


@mp.route('/term/<modality>/<text>/')
@mp.template('term.html', views=['tagcloud'])
@mp.ui_for(Term)
class _:
    @classmethod
    def from_url(cls, modality, text):
        term = db.session.query(Term).filter(Term.text == text) \
            .join(Modality).filter(Modality.name == modality) \
            .options(sa.orm.joinedload(Term.documents)
                     .joinedload(DocumentTerm.document)
                     .joinedload(Document.terms_authors).joinedload(DocumentTerm.term)) \
            .one()
        return cls(term)

    def to_url(self):
        return {'modality': self.model.modality.name}

    @property
    def root_topic(self):
        topicterms = db.session.query(TopicTerm) \
            .filter(TopicTerm.modality_id == self.model.modality_id) \
            .filter(TopicTerm.term_id == self.model.id) \
            .filter(TopicTerm.prob_wt > 0.001) \
            .cte('topicterms')

        topics = load_hierarchy(topicterms)
        for tt in db.session.query(TopicTerm).select_entity_from(topicterms):
            old_val = topics[tt.topic_id].terms
            if tt not in old_val:
                sa.orm.attributes.set_committed_value(topics[tt.topic_id], 'terms', old_val + [tt])

        return topics[0]


@mp.route('/topic/<int:id>/')
@mp.template('topic.html', views=['hierarchy'])
@mp.ui_for(Topic)
class _:
    @classmethod
    def from_url(cls, id):
        topic_docs = db.session.query(Topic).filter_by(id=id) \
            .outerjoin(Topic.documents).order_by(DocumentTopic.prob_td.desc()) \
            .options(sa.orm.contains_eager(Topic.documents)
                     .joinedload(DocumentTopic.document)
                     .joinedload(Document.terms_authors)) \
            .one()
        topic_terms = db.session.query(Topic).filter_by(id=id) \
            .outerjoin(Topic.terms).order_by(TopicTerm.prob_wt.desc()).limit(100) \
            .options(sa.orm.contains_eager(Topic.terms)) \
            .one()
        sa.orm.attributes.set_committed_value(topic_docs, 'terms', topic_terms.terms)
        return cls(topic_docs)


@mp.template('relations_views.html', views=None)
@mp.ui_for(DocumentTopic)
@mp.ui_for(DocumentTerm)
@mp.ui_for(TopicTerm)
class _:
    pass


@mp.template('assessments.html')
@mp.route('/assess/<ass_cls>/', methods=['POST'])
@mp.ui_for(AssessmentMixin)
class _:
    @classmethod
    def from_url(cls, ass_cls):
        ass_cls = globals()[ass_cls]
        assessment = ass_cls()
        if 'username' in session:
            assessment.username = session['username']
        assessment.technical_info = {
            'user_agent': request.user_agent.string,
            'referrer': request.referrer,
            'access_route': request.access_route
        }
        for k, v in request.args.items():
            setattr(assessment, k, v)
        for k, v in request.form.items():
            setattr(assessment, k, v)
        return cls(assessment)

    def to_url(self):
        return {
            'ass_cls': self.model.__class__.__name__,
            **{local.name: getattr(self.model.src, remote.name)
               for local, remote in self.model.__class__.src.property.local_remote_pairs},
            **{k: v
               for k, v in self.model.__dict__.items()
               if not k.startswith('_') and k != 'src'},
        }

    def __call__(self):
        res = repr(self.model)
        db.session.add(self.model)
        db.session.commit()
        return res


@mp.template('a_results.html')
@mp.route('/assessment_results/')
class _:
    @property
    def topics_ass_count(self):
        return db.session.query(ATopicTerm).count()

    @property
    def topics_score(self):
        prob_positive = sa.func.sum(TopicTerm.prob_wt).filter(ATopicTerm.value == 1)
        prob_negative = sa.func.sum(TopicTerm.prob_wt).filter(ATopicTerm.value == -1)
        return db.session.query((prob_positive - prob_negative) / (prob_positive + prob_negative)) \
            .select_from(ATopicTerm).join(ATopicTerm.src).scalar()

    @property
    def topics(self):
        prob_positive = sa.func.coalesce(sa.func.sum(TopicTerm.prob_wt).filter(ATopicTerm.value == 1), 0)
        prob_negative = sa.func.coalesce(sa.func.sum(TopicTerm.prob_wt).filter(ATopicTerm.value == -1), 0)
        q = db.session.query(
            Topic,
            sa.func.count(ATopicTerm.value).label('count'),
            sa.func.count(ATopicTerm.value).filter(ATopicTerm.value == 1).label('count_positive'),
            ((prob_positive - prob_negative) / sa.func.nullif(prob_positive + prob_negative, 0)).label('score')
        ) \
            .join(Topic.terms).outerjoin(TopicTerm.assessments) \
            .group_by(Topic.id) \
            .order_by(sa.desc('score').nullslast(), sa.desc('count'))
        topics = q.all()

        rn_terms = sa.func.row_number().over(partition_by=(TopicTerm.topic_id, TopicTerm.modality_id),
                                             order_by=TopicTerm.prob_wt.desc())
        topics_with_terms = db.session.query(Topic, TopicTerm, rn_terms) \
            .outerjoin(Topic.terms) \
            .from_self(Topic) \
            .filter(rn_terms <= 15) \
            .order_by(Topic.id, TopicTerm.modality_id, TopicTerm.prob_wt.desc()) \
            .options(sa.orm.contains_eager(Topic.terms))
        topics_with_terms.all()

        for r in topics:
            r.Topic.score = r.score
            r.Topic.count = r.count
            r.Topic.ass_terms = []

        count_positive = sa.func.count(ATopicTerm.value).filter(ATopicTerm.value == 1)
        count_negative = sa.func.count(ATopicTerm.value).filter(ATopicTerm.value == -1)
        q = db.session.query(
            TopicTerm,
            ((count_positive - count_negative) / (count_positive + count_negative)).label('score')
        ) \
            .join(TopicTerm.assessments) \
            .group_by(TopicTerm) \
            .order_by(sa.desc('score'), TopicTerm.prob_wt.desc()) \
            .options(sa.orm.lazyload(TopicTerm.topic), sa.orm.subqueryload(TopicTerm.term))
        tterms = q.all()

        for r in tterms:
            r.TopicTerm.topic.ass_terms.append(r)

        return topics

    @property
    def documents(self):
        prob_positive = sa.func.coalesce(sa.func.sum(DocumentTopic.prob_td).filter(ADocumentTopic.value == 1), 0)
        prob_negative = sa.func.coalesce(sa.func.sum(DocumentTopic.prob_td).filter(ADocumentTopic.value == -1), 0)
        score = (prob_positive - prob_negative) / 1
        q = db.session.query(
            Document,
            sa.func.count(ADocumentTopic.value).label('count'),
            score.label('score')
        ) \
            .join(Document.topics).join(DocumentTopic.assessments) \
            .group_by(Document.id) \
            .order_by(sa.func.random()).limit(100) \
            .from_self() \
            .order_by(score.desc().nullslast(), sa.desc('count'))

        docs = q.all()
        return docs


if not mp.app.debug:
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
