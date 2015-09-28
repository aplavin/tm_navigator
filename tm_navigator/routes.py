import traceback
from main import mp, db
from flask import request, session, redirect
from models import *
from assessment_models import *
import sqlalchemy as sa
import sqlalchemy_searchable as searchable
from cached_property import cached_property


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
                                         order_by=TopicTerm.probability.desc())
    topics_with_terms = db.session.query(Topic, TopicTerm, rn_terms) \
        .outerjoin(Topic.terms) \
        .join(filtered_topics, Topic.id == filtered_topics.c.id) \
        .from_self(Topic) \
        .filter(rn_terms <= 15) \
        .order_by(Topic.id, TopicTerm.modality_id, TopicTerm.probability.desc()) \
        .options(sa.orm.contains_eager(Topic.terms))
    topics_with_terms.all()

    return topics


@mp.route('/document/<slug>/')
@mp.template('document.html')
@mp.ui_for(Document)
class _:
    @classmethod
    def from_url(cls, slug):
        document = db.session.query(Document).filter_by(slug=slug).one()
        return cls(document)

    @property
    def root_topic(self):
        doctopics = db.session.query(DocumentTopic) \
            .filter(DocumentTopic.document_id == self.model.id) \
            .filter(DocumentTopic.probability > 0.001) \
            .cte('doctopics')
    
        topics = load_hierarchy(doctopics)
        db.session.query(Topic).outerjoin(doctopics)\
            .options(sa.orm.contains_eager(Topic.documents, alias=doctopics).noload(DocumentTopic.document))\
            .all()

        return topics[0]

    @property
    def html(self):
        html = self.model.html

        html_new = ''
        html_pos = 0
        for cnt in self.model.contents:
            html_new += html[html_pos:cnt.start_pos]
            html_new += '<span data-word="%d" data-color="%d"><a href="#">' % (cnt.term_id, cnt.topic_id)
            html_new += html[cnt.start_pos:cnt.end_pos]
            html_new += '</a></span>'
            html_pos = cnt.end_pos
        html_new += html[html_pos:]

        html = re.search(r'</header>(.*)</body>', html_new, re.DOTALL).group(1)
        html = re.sub(r'<img class="(\w+)" src="\w+/(eqn\d+).png".*?/>',
                      r'<span class="sprite-\2"></span>',
                      html, flags=re.DOTALL | re.MULTILINE)

        return html


@mp.route('/term/<modality>/<text>/')
@mp.template('term.html', views=['tagcloud'])
@mp.ui_for(Term)
class _:
    @classmethod
    def from_url(cls, modality, text):
        term = db.session.query(Term).filter(Term.text == text)\
            .join(Modality).filter(Modality.name == modality)\
            .one()
        return cls(term)

    def to_url(self):
        return {'modality': self.model.modality.name}

    @property
    def root_topic(self):
        topicterms = db.session.query(TopicTerm) \
            .filter(TopicTerm.modality_id == self.model.modality_id) \
            .filter(TopicTerm.term_id == self.model.id) \
            .filter(TopicTerm.probability > 0.001) \
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
        topic_docs = db.session.query(Topic).filter_by(id=id)\
            .outerjoin(Topic.documents).order_by(DocumentTopic.probability.desc())\
            .options(sa.orm.contains_eager(Topic.documents))\
            .one()
        topic_terms = db.session.query(Topic).filter_by(id=id)\
            .outerjoin(Topic.terms).order_by(TopicTerm.probability.desc()).limit(100)\
            .options(sa.orm.contains_eager(Topic.terms))\
            .one()
        sa.orm.attributes.set_committed_value(topic_docs, 'terms', topic_terms.terms)
        return cls(topic_docs)


@mp.template('relations_views.html', views=None)
@mp.ui_for(DocumentTopic)
@mp.ui_for(DocumentTerm)
@mp.ui_for(TopicTerm)
class _: pass


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
