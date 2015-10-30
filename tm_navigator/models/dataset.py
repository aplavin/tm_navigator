import sqlalchemy as sa
import sqlalchemy.ext.hybrid
from sqlalchemy_utils.types import TSVectorType
from sqlalchemy_utils import aggregated
from models.public import *


class Modality(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.Text, nullable=False, unique=True)

    @aggregated('terms',
                sa.Column(sa.Integer, nullable=False, server_default=sa.literal(0)))
    def count(self):
        return sa.func.count()


class Document(Base):
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


class DocumentTerm(Base):
    document_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), primary_key=True)
    modality_id = sa.Column(sa.Integer, sa.ForeignKey(Modality.id), primary_key=True)
    term_id = sa.Column(sa.Integer, primary_key=True)
    count = sa.Column(sa.Integer, nullable=False)

    document = sa.orm.relationship(Document, lazy='joined',
                                   backref=sa.orm.backref('terms', order_by=count.desc()))
    term = sa.orm.relationship(Term, lazy='joined',
                               backref=sa.orm.backref('documents', order_by=count.desc()))
    modality = sa.orm.relationship(Modality, viewonly=True, lazy='select',
                                   backref=sa.orm.backref('documents', viewonly=True))

    __table_args__ = (
        sa.ForeignKeyConstraint([modality_id, term_id], [Term.modality_id, Term.id]),
        sa.Index('dt_term_ix', modality_id, term_id),
    )


class DocumentContent(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    document_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), nullable=False)
    modality_id = sa.Column(sa.Integer, sa.ForeignKey(Modality.id), nullable=False)
    term_id = sa.Column(sa.Integer, nullable=False)
    start_pos = sa.Column(sa.Integer, nullable=False)
    end_pos = sa.Column(sa.Integer, nullable=False)

    document = sa.orm.relationship(Document, backref=sa.orm.backref('contents', order_by=start_pos))
    term = sa.orm.relationship(Term)
    modality = sa.orm.relationship(Modality, viewonly=True)

    __table_args__ = (
        sa.ForeignKeyConstraint([modality_id, term_id], [Term.modality_id, Term.id]),
        sa.UniqueConstraint(document_id, modality_id, start_pos, term_id),
    )


models_dataset = (Modality, Document, Term, DocumentTerm, DocumentContent)
__all__ = ('Base', 'SchemaMixin', 'models_public') + tuple(m.__name__ for m in models_public) + \
          ('models_dataset',) + tuple(m.__name__ for m in models_dataset)
