#!/usr/bin/env python3
import sqlalchemy as sa
import sqlalchemy.exc
import sys
from contextlib import contextmanager
from pathlib import Path
import click
import csv

sys.path.append('tm_navigator')
from tm_navigator.models import *

engine = sa.create_engine('postgresql+psycopg2://postgres@localhost/tm_navigator')
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


def check_files(directory, expected_names, extension='.csv', cli=True):
    file_names = {p.name for p in directory.iterdir() if p.is_file()}
    expected_files = {t + extension for t in expected_names}

    if expected_files & file_names:
        s = 'Found files {}.'.format(
            ', '.join('"{}"'.format(f) for f in sorted(expected_files & file_names)))
        if cli:
            click.secho(s, fg='green')
        else:
            print(s)
    if expected_files - file_names:
        s = 'Not found files {}.'.format(
            ', '.join('"{}"'.format(f) for f in sorted(expected_files - file_names)))
        if cli:
            click.secho(s, fg='red')
            click.echo('Will try to continue with the files present.')
        else:
            print(s)
            print('Will try to continue with the files present.')


def delete_data_for(session, models, cli=True):
    def delete_data(iter_func=lambda: None):
        for table in reversed(Base.metadata.sorted_tables):
            matching_models = [m for m in models if m.__table__ == table]
            if not matching_models:
                continue
            model = matching_models[0]
            session.query(model).delete()
            iter_func()

    if cli:
        with click.progressbar(label='Deleting data', length=len(models)) as pbar:
            delete_data(lambda: pbar.update(1))
    else:
        delete_data()


def load_data_for(session, models, directory, cli=True):
    def load_data(iter_func=lambda: None):
        for table in Base.metadata.sorted_tables:
            matching_models = [m for m in models if m.__table__ == table]
            if not matching_models:
                continue
            model = matching_models[0]

            file = directory / '{}.csv'.format(model.__tablename__)
            copy_from_csv(session, model, file)
            iter_func()

    if cli:
        with click.progressbar(label='Loading data', length=len(models)) as pbar:
            load_data(lambda: pbar.update(1))
            
    else:
        load_data()


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
                               ', '.join('{cnt} {t} at lvl {lvl}'.format(lvl=lvl, t='background' if bck else '', cnt=cnt)
                                         for lvl, bck, cnt in session.query(Topic.level, Topic.is_background, sa.func.count())
                                         .group_by(Topic.level, Topic.is_background).order_by(Topic.level, Topic.is_background)))
                except sa.exc.ProgrammingError:
                    click.echo('    Error - can\'t find data')
                    session.rollback()
                click.echo()


def add_dataset_():
    with session_scope() as session:
        SchemaMixin.activate_public_schema(session)

        ds = DatasetMeta()
        session.add(ds)
        session.flush()

        ds.activate_schemas()
        Base.metadata.create_all(engine,
                                 tables=map(lambda c: c.__table__, models_dataset))
        return ds.id

@cli.command()
def add_dataset():
    dataset_id = add_dataset_()
    click.echo('Added Dataset #{id}'.format(id=dataset_id))

def load_dataset_(dataset_id, title, directory, cli=False):
    directory = Path(directory)
    target_models = models_dataset

    check_files(directory, [m.__tablename__ for m in target_models], cli=cli)
    if cli:
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
        delete_data_for(session, models, cli)
        load_data_for(session, models, directory, cli)

@cli.command()
@click.option('-d', '--dataset-id', type=int, required=True)
@click.option('-t', '--title', type=str)
@click.option('-dir', '--directory', type=dir_type, required=True)
def load_dataset(dataset_id, title, directory):
    load_dataset_(dataset_id, title, directory, cli=True)

def add_topicmodel_(dataset_id):
    with session_scope() as session:
        SchemaMixin.activate_public_schema(session)

        ds = session.query(DatasetMeta).filter_by(id=dataset_id).one()
        tm = TopicModelMeta(dataset=ds)
        session.add(tm)
        session.flush()
        tm.domains.append(TopicModelDomain(domain='{}.'.format(tm.id)))

        tm.activate_schemas()
        Base.metadata.create_all(engine,
                                 tables=map(lambda c: c.__table__, models_topic + models_assessment))

        return tm.id

@cli.command()
@click.option('-d', '--dataset-id', type=int, required=True)
def add_topicmodel(dataset_id):
    topicmodel_id = add_topicmodel_(dataset_id)
    click.echo('Added Topic Model #{id} for Dataset #{did}'.format(id=topicmodel_id, did=dataset_id))

def load_topicmodel_(topicmodel_id, title, directory, cli=False):
    directory = Path(directory)
    target_models = models_topic

    check_files(directory, [m.__tablename__ for m in target_models], cli=cli)
    if cli:
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
        delete_data_for(session, models, cli)
        load_data_for(session, models, directory, cli)

@cli.command()
@click.option('-m', '--topicmodel-id', type=int, required=True)
@click.option('-t', '--title', type=str)
@click.option('-dir', '--directory', type=dir_type, required=True)
def load_topicmodel(topicmodel_id, title, directory):
    load_topicmodel_(topicmodel_id, title, directory, cli=True)

def dump_assessments_(topicmodel_id, directory):
    directory = Path(directory)
    with session_scope() as session:
        SchemaMixin.activate_public_schema(session)
        tm = session.query(TopicModelMeta).filter_by(id=topicmodel_id).one()
        tm.activate_schemas()

        assessments = session.query(ATopic).all()
        topic_count = session.query(Topic).count() - 1

        grades = [None for i in range(topic_count)]
        for assessment in assessments:
            grades[assessment.topic_id - 1] = assessment.value
        with open(directory.joinpath('topic_assessments.csv'), 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['topic_id', 'value'])
            for idx, grade in enumerate(grades):
                writer.writerow([idx + 1, grade])

@cli.command()
@click.option('-m', '--topicmodel-id', type=int, required=True)
@click.option('-dir', '--directory', type=dir_type, required=True)
def dump_assessments(topicmodel_id, directory):
    dump_assessments_(topicmodel_id, directory)
    
if __name__ == '__main__':
    cli()
