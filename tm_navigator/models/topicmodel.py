import sqlalchemy as sa
import sqlalchemy.ext.hybrid
from sqlalchemy_utils import aggregated
from models.dataset import *


class DocumentSimilarity(Base):
    a_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), primary_key=True)
    b_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), primary_key=True)
    similarity = sa.Column(sa.Float, nullable=False)

    a = sa.orm.relationship(Document, lazy='joined',
                            backref=sa.orm.backref('similar', order_by=similarity.desc()),
                            foreign_keys=a_id)
    b = sa.orm.relationship(Document, lazy='joined', foreign_keys=b_id)


class TermSimilarity(Base):
    a_modality_id = sa.Column(sa.Integer, primary_key=True)
    a_id = sa.Column(sa.Integer, primary_key=True)
    b_modality_id = sa.Column(sa.Integer, primary_key=True)
    b_id = sa.Column(sa.Integer, primary_key=True)
    similarity = sa.Column(sa.Float, nullable=False)

    a = sa.orm.relationship(Term, lazy='joined',
                            backref=sa.orm.backref('similar', order_by=similarity.desc()),
                            foreign_keys=[a_modality_id, a_id])
    b = sa.orm.relationship(Term, lazy='joined', foreign_keys=[b_modality_id, b_id])

    __table_args__ = (
        sa.ForeignKeyConstraint([a_modality_id, a_id], [Term.modality_id, Term.id]),
        sa.ForeignKeyConstraint([b_modality_id, b_id], [Term.modality_id, Term.id]),
    )


class Topic(Base):
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
        return sa.func.coalesce(sa.func.sum(DocumentTopic.prob_td), 0)


class TopicSimilarity(Base):
    a_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    b_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    similarity = sa.Column(sa.Float, nullable=False)

    a = sa.orm.relationship(Topic, lazy='joined',
                            backref=sa.orm.backref('similar', order_by=similarity.desc()),
                            foreign_keys=a_id)
    b = sa.orm.relationship(Topic, lazy='joined', foreign_keys=b_id)


class TopicEdge(Base):
    parent_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    child_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    probability = sa.Column(sa.Float, nullable=False)

    parent = sa.orm.relationship(Topic, lazy='joined',
                                 backref=sa.orm.backref('children', order_by=probability.desc()),
                                 foreign_keys=parent_id)
    child = sa.orm.relationship(Topic, lazy='joined', backref='parents', foreign_keys=child_id)


class DocumentTopic(Base):
    document_id = sa.Column(sa.Integer, sa.ForeignKey(Document.id), primary_key=True)
    topic_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    prob_td = sa.Column(sa.Float, nullable=False)
    prob_dt = sa.Column(sa.Float, nullable=False)

    document = sa.orm.relationship(Document, lazy='joined',
                                   backref=sa.orm.backref('topics', order_by=prob_td.desc()))
    topic = sa.orm.relationship(Topic, lazy='joined',
                                backref=sa.orm.backref('documents', order_by=prob_td.desc()))


class TopicTerm(Base):
    topic_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), primary_key=True)
    modality_id = sa.Column(sa.Integer, sa.ForeignKey(Modality.id), primary_key=True)
    term_id = sa.Column(sa.Integer, primary_key=True)
    prob_wt = sa.Column(sa.Float, nullable=False)
    prob_tw = sa.Column(sa.Float, nullable=False)

    topic = sa.orm.relationship(Topic, lazy='joined',
                                backref=sa.orm.backref('terms', order_by=prob_wt.desc()))
    term = sa.orm.relationship(Term, lazy='joined',
                               backref=sa.orm.backref('topics', order_by=prob_wt.desc()))
    modality = sa.orm.relationship(Modality, viewonly=True, lazy='select',
                                   backref=sa.orm.backref('topics', viewonly=True))

    __table_args__ = (
        sa.ForeignKeyConstraint([modality_id, term_id], [Term.modality_id, Term.id]),
    )


class DocumentContentTopic(Base):
    document_content_id = sa.Column(sa.Integer, sa.ForeignKey(DocumentContent.id), nullable=False, primary_key=True)
    topic_id = sa.Column(sa.Integer, sa.ForeignKey(Topic.id), nullable=False, primary_key=True)
    # topic_probability = sa.Column(sa.Float, nullable=False)

    document_content = sa.orm.relationship(DocumentContent, backref=sa.orm.backref('topics'))
    topic = sa.orm.relationship(Topic)


models_topic = (DocumentSimilarity, TermSimilarity, TopicSimilarity,
                Topic, TopicEdge, DocumentTopic, TopicTerm, DocumentContentTopic)
__all__ = ('Base', 'SchemaMixin', 'models_public') + tuple(m.__name__ for m in models_public) + \
          ('models_dataset',) + tuple(m.__name__ for m in models_dataset) + \
          ('models_topic',) + tuple(m.__name__ for m in models_topic)
