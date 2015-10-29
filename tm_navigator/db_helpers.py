import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy_searchable import make_searchable
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.dialects import postgresql as pg_dialect
import inflection


class Base(object):
    @declared_attr
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


Base = declarative_base(cls=Base)
make_searchable()


def create_aggregate_with_orderby(name, coltype):
    class AggregateElement(ColumnElement):
        type = coltype

        def __init__(self, *exprs, order_by=None):
            self.exprs = exprs
            self.order_by = order_by

    @compiles(AggregateElement)
    def compile_aggregate(element, compiler, **kw):
        result = ', '.join(compiler.process(expr)
                           for expr in element.exprs)
        if element.order_by is not None:
            result += ' ORDER BY %s' % compiler.process(element.order_by)
        result = '%s(%s)' % (name, result)
        return result

    setattr(sa.func, name, AggregateElement)


for name, type in [('array_agg', pg_dialect.ARRAY(sa.Integer, as_tuple=True)), ('string_agg', sa.String)]:
    create_aggregate_with_orderby(name, type)
