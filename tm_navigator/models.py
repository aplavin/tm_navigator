import re
import sqlalchemy as sa
import sqlalchemy.ext.hybrid
import sqlalchemy.ext.declarative as sa_dec
from sqlalchemy.dialects import postgresql
from sqlalchemy_searchable import make_searchable
from sqlalchemy_utils.types import TSVectorType
from sqlalchemy_utils import aggregated
import inflection
from db_helpers import *


class Base(object):
    @sa_dec.declared_attr
    def __tablename__(cls):
        return inflection.tableize(cls.__name__)

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
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.Text, nullable=False, unique=True)

    @aggregated('terms',
                sa.Column(sa.Integer, nullable=False, server_default=sa.literal(0)))
    def count(self):
        return sa.func.count()


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
    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.Text, nullable=False)
    file_name = sa.Column(sa.Text, nullable=False, unique=True)
    slug = sa.Column(sa.Text, nullable=False, unique=True)
    source = sa.Column(sa.Text)

    text = sa.orm.deferred(sa.Column(sa.Text))
    html = sa.orm.deferred(sa.Column(sa.Text))

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
        return self.source # re.sub(r'^([a-z]+)(\d+)-pdfs/.+', r'\1-\2', self.file_name).upper()


class DocumentSimilarity(Base):
    a_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), primary_key=True)
    b_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), primary_key=True)
    similarity = sa.Column(sa.Float, nullable=False)

    a = sa.orm.relationship(Document, lazy='joined',
                            backref=sa.orm.backref('similar', order_by=similarity.desc()),
                            foreign_keys=a_id)
    b = sa.orm.relationship(Document, lazy='joined', foreign_keys=b_id)


class Term(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    modality_id = sa.Column(sa.Integer, sa.ForeignKey(Modality.id), primary_key=True)
    text = sa.Column(sa.Text, nullable=False)

    modality = sa.orm.relationship(Modality, backref='terms', lazy='joined')

    @aggregated('documents',
                sa.Column(sa.Integer, nullable=False, server_default=sa.literal(0)))
    def count(self):
        return sa.func.coalesce(sa.func.sum(DocumentTerm.count), 0)

    __table_args__ = (
        sa.UniqueConstraint(modality_id, text),
    )


class Topic(Base, ModalityFilterMixin):
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.Text, unique=True)
    type = sa.Column(sa.Enum('foreground', 'background', name='fgbg_enum'), nullable=False)

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

    @aggregated('documents',
                sa.Column(sa.Float, nullable=False, server_default=sa.literal(0)))
    def probability(self):
        # TODO: correct computation!
        return sa.func.coalesce(sa.func.sum(DocumentTopic.probability), 0)


class TopicEdge(Base):
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    child_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    probability = sa.Column(sa.Float, nullable=False)

    parent = sa.orm.relationship(Topic, lazy='joined',
                                 backref=sa.orm.backref('children', order_by=probability.desc()),
                                 foreign_keys=parent_id)
    child = sa.orm.relationship(Topic, lazy='joined', backref='parents', foreign_keys=child_id)


class DocumentTerm(Base):
    document_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), primary_key=True)
    modality_id = sa.Column(sa.Integer, sa.ForeignKey(Modality.id), primary_key=True)
    term_id = sa.Column(sa.Integer, primary_key=True)
    count = sa.Column(sa.Integer, nullable=False)

    document = sa.orm.relationship(Document, lazy='joined',
                                   backref=sa.orm.backref('terms', order_by=count.desc(), lazy='dynamic'))
    term = sa.orm.relationship(Term, lazy='joined',
                               backref=sa.orm.backref('documents', order_by=count.desc()))
    modality = sa.orm.relationship(Modality, viewonly=True, lazy='select',
                                   backref=sa.orm.backref('documents', viewonly=True))

    __table_args__ = (
        sa.ForeignKeyConstraint([modality_id, term_id], [Term.modality_id, Term.id]),
        sa.Index('dt_term_ix', modality_id, term_id),
        sa.Index('dt_doc_ix', document_id),
    )


class DocumentTopic(Base):
    document_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), primary_key=True)
    topic_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    probability = sa.Column(sa.Float, nullable=False)

    document = sa.orm.relationship(Document, lazy='joined',
                                   backref=sa.orm.backref('topics', order_by=probability.desc()))
    topic = sa.orm.relationship(Topic, lazy='joined',
                                backref=sa.orm.backref('documents', order_by=probability.desc()))


class TopicTerm(Base):
    topic_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    modality_id = sa.Column(sa.Integer, sa.ForeignKey(Modality.id), primary_key=True)
    term_id = sa.Column(sa.Integer, primary_key=True)
    probability = sa.Column(sa.Float)

    topic = sa.orm.relationship(Topic, lazy='joined',
                                backref=sa.orm.backref('terms', order_by=probability.desc()))
    term = sa.orm.relationship(Term, lazy='joined',
                               backref=sa.orm.backref('topics', order_by=probability.desc()))
    modality = sa.orm.relationship(Modality, viewonly=True, lazy='select',
                                   backref=sa.orm.backref('topics', viewonly=True))

    __table_args__ = (
        sa.ForeignKeyConstraint([modality_id, term_id], [Term.modality_id, Term.id]),
    )


class DocumentContent(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    document_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), nullable=False)
    modality_id = sa.Column(sa.Integer, sa.ForeignKey(Modality.id), nullable=False)
    term_id = sa.Column(sa.Integer, nullable=False)
    start_pos = sa.Column(sa.Integer, nullable=False)
    end_pos = sa.Column(sa.Integer, nullable=False)
    topic_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), nullable=False)
    # topic_probability = sa.Column(sa.Float, nullable=False)

    document = sa.orm.relationship(Document, backref=sa.orm.backref('contents', order_by=start_pos))
    term = sa.orm.relationship(Term)
    modality = sa.orm.relationship(Modality)
    topic = sa.orm.relationship(Topic)

    __table_args__ = (
        sa.ForeignKeyConstraint([modality_id, term_id], [Term.modality_id, Term.id]),
        sa.UniqueConstraint(document_id, modality_id, term_id, start_pos),
    )
