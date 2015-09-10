from models import *
from sqlalchemy.dialects import postgresql as pg_dialect


class AssessmentMixin(object):
    id = sa.Column(sa.Integer, primary_key=True)
    username = sa.Column(sa.String)
    date = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False)
    technical_info = sa.Column(pg_dialect.JSONB, nullable=False)


class ATopic(Base, AssessmentMixin):
    topic_id = sa.Column(sa.Integer, nullable=False)
    value = sa.Column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint('username', topic_id),
        sa.ForeignKeyConstraint([topic_id],
                                [Topic.id]),
    )

    src = sa.orm.relationship(Topic, backref='assessments')


class ATopicEdge(Base, AssessmentMixin):
    parent_id = sa.Column(sa.Integer, nullable=False)
    child_id = sa.Column(sa.Integer, nullable=False)
    child_type = sa.Column(sa.Enum('parent', 'child', name='pc_enum'), nullable=False)
    value = sa.Column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint('username', parent_id, child_id),
        sa.ForeignKeyConstraint([parent_id, child_id],
                                [TopicEdge.parent_id, TopicEdge.child_id]),
    )

    src = sa.orm.relationship(TopicEdge, backref='assessments')


class ADocumentSimilarity(Base, AssessmentMixin):
    a_id = sa.Column(sa.Integer, nullable=False)
    b_id = sa.Column(sa.Integer, nullable=False)
    value = sa.Column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint('username', a_id, b_id),
        sa.ForeignKeyConstraint([a_id, b_id],
                                [DocumentSimilarity.a_id, DocumentSimilarity.b_id]),
    )

    src = sa.orm.relationship(DocumentSimilarity, backref='assessments')


class ADocumentTopic(Base, AssessmentMixin):
    document_id = sa.Column(sa.Integer, nullable=False)
    topic_id = sa.Column(sa.Integer, nullable=False)
    child_type = sa.Column(sa.Enum('document', 'topic', name='dt_enum'), nullable=False)
    value = sa.Column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint('username', document_id, topic_id),
        sa.ForeignKeyConstraint([document_id, topic_id],
                                [DocumentTopic.document_id, DocumentTopic.topic_id]),
    )

    src = sa.orm.relationship(DocumentTopic, backref='assessments')


class ATopicTerm(Base, AssessmentMixin):
    topic_id = sa.Column(sa.Integer, nullable=False)
    modality_id = sa.Column(sa.Integer, nullable=False)
    term_id = sa.Column(sa.Integer, nullable=False)
    child_type = sa.Column(sa.Enum('topic', 'term', name='tt_enum'), nullable=False)
    value = sa.Column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint('username', topic_id, modality_id, term_id),
        sa.ForeignKeyConstraint([topic_id, modality_id, term_id],
                                [TopicTerm.topic_id, TopicTerm.modality_id, TopicTerm.term_id]),
    )

    src = sa.orm.relationship(TopicTerm, backref='assessments')
