#!/usr/bin/env python3.5
import sqlalchemy as sa
import sqlalchemy.exc
import sys
from contextlib import contextmanager
from pathlib import Path
import click

sys.path.append('tm_navigator')
from tm_navigator.models import *

engine = sa.create_engine('postgresql+psycopg2://@localhost/tm_navigator_dev')
sa.orm.configure_mappers()
Session = sa.orm.sessionmaker(bind=engine)


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


from sqlalchemy_utils import aggregates

aggregates.local_condition = lambda prop, objects: sa.literal(True)


class ListSession(list):
    def execute(self, query):
        return self._session.execute(query)


def update_aggregates(session, *classes_modified):
    ls = ListSession([c() for c in classes_modified])
    ls._session = session
    aggregates.manager.construct_aggregate_queries(ls, None)


def copy_from_csv(session, model, csv_file):
    with session.connection().connection.cursor() as cursor, csv_file.open() as csv_f:
        fieldnames = csv_f.readline()
        cursor.copy_expert('copy {0} ({1}) from stdin with csv'.format(model.__tablename__, fieldnames), csv_f)

    update_aggregates(session, model)


def check_files(directory, expected_names, extension='.csv'):
    file_names = {p.name for p in directory.iterdir() if p.is_file()}
    expected_files = {t + extension for t in expected_names}

    click.secho('Found files {}.'.format(
        ', '.join('"{}"'.format(f) for f in sorted(expected_files & file_names))
    ), fg='green')
    click.secho('Not found files {}.'.format(
        ', '.join('"{}"'.format(f) for f in sorted(expected_files - file_names))
    ), fg='red')
    click.echo('Will try to continue with the files present.')


def delete_data_for(session, models):
    with click.progressbar(reversed(Base.metadata.sorted_tables), label='Deleting data', length=len(models)) as pbar:
        for table in pbar:
            matching_models = [m for m in models if m.__table__ == table]
            if not matching_models:
                continue
            model = matching_models[0]
            session.query(model).delete()


def load_data_for(session, models, directory):
    with click.progressbar(Base.metadata.sorted_tables, label='Loading data', length=len(models)) as pbar:
        for table in pbar:
            matching_models = [m for m in models if m.__table__ == table]
            if not matching_models:
                continue
            model = matching_models[0]

            file = directory / '{}.csv'.format(model.__tablename__)
            copy_from_csv(session, model, file)


@click.group()
def cli():
    pass


dir_type = click.Path(exists=True, file_okay=False, resolve_path=True)


@cli.command()
def describe():
    with session_scope() as session:
        SchemaMixin.activate_public_schema(session)
        dses = session.query(DatasetMeta).order_by(DatasetMeta.id).all()
        for ds in dses:
            ds.activate_schemas()
            click.secho('- Dataset #{id}: {title}, {ntm} models'.format(id=ds.id,
                                                                        title=ds.title or 'untitled',
                                                                        ntm=len(ds.topic_models)),
                        fg='blue')
            try:
                click.echo('  Documents: {cnt}'.format(cnt=session.query(Document).count()))
                click.echo('  Terms: ' +
                           ', '.join('{m.count} {m.name} with {nocc} occurrences'.format(m=m, nocc=nocc)
                                     for m, nocc in session.query(Modality, sa.func.count())
                                     .join(Modality.terms).join(Term.documents)
                                     .group_by(Modality).order_by(Modality.name)))
            except sa.exc.ProgrammingError:
                click.echo('  Error - can\'t find data')
                session.rollback()
            click.echo()

            for tm in ds.topic_models:
                tm.activate_schemas()
                click.secho('  - Topic Model #{id}: {title}'.format(id=tm.id, title=tm.title or 'untitled'),
                            fg='blue')
                try:
                    click.echo('    Topics: ' +
                               ', '.join('{cnt} {t} at lvl {lvl}'.format(lvl=lvl, t=t, cnt=cnt)
                                         for lvl, t, cnt in session.query(Topic.level, Topic.type, sa.func.count())
                                         .group_by(Topic.level, Topic.type).order_by(Topic.level, Topic.type)))
                except sa.exc.ProgrammingError:
                    click.echo('    Error - can\'t find data')
                    session.rollback()
                click.echo()


@cli.command()
def add_dataset():
    with session_scope() as session:
        SchemaMixin.activate_public_schema(session)

        ds = DatasetMeta()
        session.add(ds)
        session.flush()

        ds.activate_schemas()
        Base.metadata.create_all(engine,
                                 tables=map(lambda c: c.__table__, models_dataset))

        click.echo('Added Dataset #{id}'.format(id=ds.id))


@cli.command()
@click.option('-d', '--dataset-id', type=int, required=True)
@click.option('-t', '--title', type=str)
@click.option('-dir', '--directory', type=dir_type, required=True)
def load_dataset(dataset_id, title, directory):
    directory = Path(directory)
    target_models = models_dataset

    check_files(directory, [m.__tablename__ for m in target_models])
    click.confirm('Proceeding will overwrite the corresponding data in the database. Continue?',
                  abort=True, default=True)

    models = [m
              for m in target_models
              if (directory / '{}.csv'.format(m.__tablename__)).is_file()]

    with session_scope() as session:
        SchemaMixin.activate_public_schema(session)
        ds = session.query(DatasetMeta).filter_by(id=dataset_id).one()
        ds.activate_schemas()

        if title is not None:
            ds.title = title
        delete_data_for(session, models)
        load_data_for(session, models, directory)


@cli.command()
@click.option('-d', '--dataset-id', type=int, required=True)
def add_topicmodel(dataset_id):
    with session_scope() as session:
        SchemaMixin.activate_public_schema(session)

        ds = session.query(DatasetMeta).filter_by(id=dataset_id).one()
        tm = TopicModelMeta(dataset=ds)
        session.add(tm)
        session.flush()

        tm.activate_schemas()
        Base.metadata.create_all(engine,
                                 tables=map(lambda c: c.__table__, models_topic + models_assessment))

        click.echo('Added Topic Model #{id} for Dataset #{did}'.format(id=tm.id, did=ds.id))


@cli.command()
@click.option('-m', '--topicmodel-id', type=int, required=True)
@click.option('-t', '--title', type=str)
@click.option('-dir', '--directory', type=dir_type, required=True)
def load_topicmodel(topicmodel_id, title, directory):
    directory = Path(directory)
    target_models = models_topic

    check_files(directory, [m.__tablename__ for m in target_models])
    click.confirm('Proceeding will overwrite the corresponding data in the database. Continue?',
                  abort=True, default=True)

    models = [m
              for m in target_models
              if (directory / '{}.csv'.format(m.__tablename__)).is_file()]

    with session_scope() as session:
        SchemaMixin.activate_public_schema(session)
        tm = session.query(TopicModelMeta).filter_by(id=topicmodel_id).one()
        tm.activate_schemas()

        if title is not None:
            tm.title = title
        delete_data_for(session, models)
        load_data_for(session, models, directory)


if __name__ == '__main__':
    cli()
