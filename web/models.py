import re
import sqlalchemy as sa
from sqlalchemy import func, types
import sqlalchemy.ext.hybrid
import sqlalchemy.ext.declarative as sa_dec
from sqlalchemy_searchable import make_searchable
from sqlalchemy_utils.types import TSVectorType


class Base(object):
    @sa_dec.declared_attr
    def __tablename__(cls):
        return '_'.join(
            w.lower()
            for w in re.findall('[A-Z][a-z]+', cls.__name__)
        ) + 's'

    def __repr__(self):
        return "<{}({})>".format(
            self.__class__.__name__,
            ', '.join(
                ["{}={}".format(k, repr(self.__dict__[k]))
                 for k in sorted(self.__dict__.keys())
                 if k[0] != '_']
            )
        )


Base = sa_dec.declarative_base(cls=Base)
make_searchable()


class Modality(Base):
    __tablename__ = 'modalities'

    id = sa.Column(sa.types.Integer, primary_key=True)
    name = sa.Column(sa.types.Text, nullable=False, unique=True)


class ModalityFilterMixin(object):
    def modality(self, *args, **kwargs):
        outer_self = self

        class ModalityFiltered(object):
            def __getattr__(self, attr_name):
                outer_value = getattr(outer_self, attr_name)
                outer_value = outer_value.join(Modality).filter_by(*args, **kwargs)
                return outer_value

        return ModalityFiltered()


class Document(Base, ModalityFilterMixin):
    id = sa.Column(sa.types.Integer, primary_key=True)
    title = sa.Column(sa.types.Text, nullable=False)
    file_name = sa.Column(sa.types.Text, nullable=False, unique=True)
    length = sa.Column(sa.types.Integer, nullable=False)

    search_vector = sa.orm.deferred(sa.Column(TSVectorType('title', regconfig='russian')))

    @sa.ext.hybrid.hybrid_method
    def highlight(self, attribute, query):
        return sa.func.ts_headline(
            'russian',
            getattr(self, attribute),
            sa.func.to_tsquery('russian', query),
            '''highlightall=true, startsel='<span class="match">', stopsel='</span>' '''
        )

    @property
    def conference(self):
        return re.sub(r'^([a-z]+)(\d+)-pdfs/.+', r'\1-\2', self.file_name).upper()


class Term(Base):
    id = sa.Column(sa.types.Integer, primary_key=True)
    modality_id = sa.Column(sa.types.Integer, sa.ForeignKey('modalities.id'), primary_key=True)
    text = sa.Column(sa.types.Text, nullable=False)
    count = sa.Column(sa.types.Integer, nullable=False)

    modality = sa.orm.relationship('Modality', backref='terms')


class Topic(Base, ModalityFilterMixin):
    id = sa.Column(sa.types.Integer, primary_key=True)
    name = sa.Column(sa.types.Text, unique=True)
    probability = sa.Column(sa.types.Float, nullable=False)

    terms_d = sa.orm.relationship('TopicTerm', order_by='desc(TopicTerm.probability)', lazy='dynamic')

    @sa.ext.hybrid.hybrid_property
    def level(self):
        return int(self.id / 1000)

    @level.expression
    def level(self):
        return self.id / 1000

    @level.setter
    def level(self, level):
        if self.id is None:
            self.id = 0
        self.id = (self.id % 1000) + 1000 * level

    @sa.ext.hybrid.hybrid_property
    def id_in_level(self):
        return self.id % 1000

    @id_in_level.setter
    def id_in_level(self, id):
        if self.id is None:
            self.id = 0
        self.id = (self.id / 1000) * 1000 + id

    @property
    def text(self):
        return '%s-%s' % (self.level, self.name or '%02d' % self.id_in_level)


class TopicEdge(Base):
    parent_id = sa.Column(sa.types.Integer, sa.ForeignKey('topics.id'), primary_key=True)
    child_id = sa.Column(sa.types.Integer, sa.ForeignKey('topics.id'), primary_key=True)
    probability = sa.Column(sa.types.Float, nullable=False)

    parent = sa.orm.relationship('Topic', lazy='joined',
                                 backref=sa.orm.backref('children', order_by='desc(Topic.probability)'),
                                 foreign_keys=parent_id)
    child = sa.orm.relationship('Topic', lazy='joined', backref='parents', foreign_keys=child_id)


class DocumentTerm(Base):
    document_id = sa.Column(sa.types.Integer, sa.ForeignKey('documents.id'), primary_key=True)
    modality_id = sa.Column(sa.types.Integer, sa.ForeignKey('modalities.id'), primary_key=True)
    term_id = sa.Column(sa.types.Integer, primary_key=True)
    count = sa.Column(sa.types.Integer, nullable=False)

    document = sa.orm.relationship('Document', lazy='joined',
                                   backref=sa.orm.backref('terms', order_by='desc(DocumentTerm.count)', lazy='dynamic'))
    term = sa.orm.relationship('Term', lazy='joined',
                               backref=sa.orm.backref('documents', order_by='desc(DocumentTerm.count)'))
    modality = sa.orm.relationship('Modality', viewonly=True, lazy='joined',
                                   backref=sa.orm.backref('documents', viewonly=True))

    __table_args__ = (
        sa.ForeignKeyConstraint(['modality_id', 'term_id'], ['terms.modality_id', 'terms.id']),
    )


class DocumentTopic(Base):
    document_id = sa.Column(sa.types.Integer, sa.ForeignKey('documents.id'), primary_key=True)
    topic_id = sa.Column(sa.types.Integer, sa.ForeignKey('topics.id'), primary_key=True)
    probability = sa.Column(sa.types.Float, nullable=False)

    document = sa.orm.relationship('Document', lazy='joined',
                                   backref=sa.orm.backref('topics', order_by='desc(DocumentTopic.probability)'))
    topic = sa.orm.relationship('Topic', lazy='joined',
                                backref=sa.orm.backref('documents', order_by='desc(DocumentTopic.probability)'))


class TopicTerm(Base):
    topic_id = sa.Column(sa.types.Integer, sa.ForeignKey('topics.id'), primary_key=True)
    modality_id = sa.Column(sa.types.Integer, sa.ForeignKey('modalities.id'), primary_key=True)
    term_id = sa.Column(sa.types.Integer, primary_key=True)
    probability = sa.Column(sa.types.Float)

    topic = sa.orm.relationship('Topic', lazy='joined',
                                backref=sa.orm.backref('terms', order_by='desc(TopicTerm.probability)'))
    term = sa.orm.relationship('Term', lazy='joined',
                               backref=sa.orm.backref('topics', order_by='desc(TopicTerm.probability)'))
    modality = sa.orm.relationship('Modality', viewonly=True, lazy='joined',
                                   backref=sa.orm.backref('topics', viewonly=True))

    __table_args__ = (
        sa.ForeignKeyConstraint(['modality_id', 'term_id'], ['terms.modality_id', 'terms.id']),
    )
