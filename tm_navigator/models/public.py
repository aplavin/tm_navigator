import sqlalchemy as sa
import sqlalchemy.event
import sqlalchemy.orm
import sqlalchemy.schema
from models.base import Base


class SchemaMixin:
    @property
    def session(self):
        return sa.orm.Session.object_session(self)

    def create_schema(self):
        self.session.execute(sa.schema.CreateSchema(name=self.schema_name))

    def drop_schema(self):
        self.session.execute(sa.schema.DropSchema(name=self.schema_name, cascade=True))

    def exists_schema(self):
        q = self.session.execute('select count(*) > 0 from information_schema.schemata where schema_name = :schema',
                                 {'schema': self.schema_name})
        return q.scalar()

    @staticmethod
    def _activate_schemas(session, *schemas):
        dct = {'schema_%02d' % i: s for i, s in enumerate(schemas)}
        placeholders = ', '.join(sorted(':%s' % k for k in dct.keys()))
        session.execute('set search_path = %s' % placeholders, dct)
        session.commit()

    @staticmethod
    def activate_public_schema(session):
        SchemaMixin._activate_schemas(session, 'public')

    def activate_schemas(self):
        SchemaMixin._activate_schemas(self.session, *self.schemas)


class DatasetMeta(Base, SchemaMixin):
    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.Text)
    schema_name = sa.orm.column_property('tmnav_dataset_' + sa.cast(id, sa.Text))

    @property
    def schemas(self):
        return (self.schema_name, 'public')

    __table_args__ = {'schema': 'public'}


class TopicModelMeta(Base, SchemaMixin):
    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.Text)
    dataset_id = sa.Column(sa.Integer, sa.ForeignKey(DatasetMeta.id), nullable=False)
    schema_name = sa.orm.column_property('tmnav_topicmodel_' + sa.cast(id, sa.Text))

    dataset = sa.orm.relationship(DatasetMeta, lazy='joined',
                                  backref=sa.orm.backref('topic_models', lazy='joined', order_by=id))

    @property
    def schemas(self):
        return (self.schema_name, self.dataset.schema_name, 'public')

    __table_args__ = {'schema': 'public'}


class TopicModelDomain(Base):
    domain = sa.Column(sa.Text, primary_key=True)
    topic_model_id = sa.Column(sa.Integer, sa.ForeignKey(TopicModelMeta.id), nullable=False)

    topic_model = sa.orm.relationship(TopicModelMeta, lazy='joined',
                                      backref=sa.orm.backref('domains', lazy='joined', order_by=domain))

    def full_domain(self, base_domain):
        if self.domain.endswith('.'):
            return self.domain + base_domain
        else:
            return self.domain

    __table_args__ = {'schema': 'public'}


def create_schema(mapper, connection, target):
    target.create_schema()


def drop_schema(mapper, connection, target):
    print('delete event %r' % target)
    target.drop_schema()


sa.event.listen(DatasetMeta, 'after_insert', create_schema)
sa.event.listen(TopicModelMeta, 'after_insert', create_schema)
sa.event.listen(DatasetMeta, 'before_delete', drop_schema)
sa.event.listen(TopicModelMeta, 'before_delete', drop_schema)

models_public = (DatasetMeta, TopicModelMeta, TopicModelDomain)
__all__ = ('Base', 'SchemaMixin', 'models_public') + tuple(m.__name__ for m in models_public)
