#!/usr/bin/env python3.5
from collections import Counter
from recordclass import recordclass
from pathlib import Path
import csv
import numpy as np
import scipy.sparse as sp
import h5py
import re
import itertools as it
import click


def topic_id(level, t):
    """
    Compute topic ID in the database based on the level and id inside this level.

    :param level: 0 for root topic, 1 for first level and so on.
    """
    return level * 1000 + t


class CsvWriter:
    def __init__(self, directory, file_name):
        csv_file = directory / (file_name + '.csv')
        self.csv_file = csv_file
        if csv_file.exists():
            if not click.confirm('File "{}" already exists, overwrite?'.format(csv_file.name)):
                click.secho('Skipped', fg='blue')
                self.csv_file = None
        self.rows = iter(())

    def append_rows(self, new_rows):
        self.rows = it.chain(self.rows, new_rows)

    def __lshift__(self, new_rows):
        self.append_rows(new_rows)

    def __enter__(self):
        if self.csv_file:
            click.secho('Preparing rows for "{}"...'.format(self.csv_file.name), fg='blue')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type or not self.csv_file:
            return

        click.secho('Writing rows to "{}"... '.format(self.csv_file.name), nl=False, fg='blue')

        rows_cnt = it.count()
        rows = (r for r, c in zip(self.rows, rows_cnt))

        firstrow = next(rows)
        fieldnames = firstrow.keys()

        with self.csv_file.open('w') as csv_f:
            writer = csv.DictWriter(csv_f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(firstrow)
            writer.writerows(rows)

        click.secho('{} written.'.format(next(rows_cnt)), fg='green')


@click.group(chain=True)
@click.option('-dir', '--directory', help='Working directory, both for input and output files.',
              type=click.Path(exists=True, file_okay=False, resolve_path=True), required=True)
@click.pass_context
def cli(ctx, directory):
    """
    Generate tables in CSV format, which can be loaded into database by db_manage.py.
    Each command generates some set of tables, see below.
    """
    ctx.obj.directory = Path(directory)


@cli.command()
@click.pass_context
def dataset_basic(ctx):
    """
    Required dataset tables.
    """
    with CsvWriter(ctx.obj.directory, 'modalities') as out:
        out << [dict(id=1, name='words'),
                dict(id=2, name='authors')]  # these two modalities are required

    with h5py.File('data/data.hdf') as h5f:
        metadata = h5f['metadata'][...]  # contains basic metadata for documents like ids, titles, authors

    with CsvWriter(ctx.obj.directory, 'documents') as out:
        out << (
            dict(id=i,
                 title=t['title'],
                 file_name=t['filename'],  # currently not used by navigator, but supposed to be the relative filename
                 slug=t['slug'],  # unique string, identifying the document - appears in short list and URLs
                 # source is displayed as-is, e.g. conference name
                 source=re.sub(r'^\d{4}-([A-Z]+)(\d+)/.+', r'\1-\2', t['filename']),
                 html=open('data/html_sprites/%s.html' % t['filename']).read()  # the HTML content of the document
                 )
            for i, t in enumerate(metadata)
        )

    doc_authors = [(i, author.strip())
                   for i, m in enumerate(metadata)
                   for author in m['authors'].split(',')]
    authors = {a for d, a in doc_authors}
    authors_terms = {a: dict(id=i, modality_id=2, text=a)
                     for i, a in enumerate(authors)}

    with open('data/dictionary.mmro.txt') as f, \
            CsvWriter(ctx.obj.directory, 'terms') as out:
        out << authors_terms.values()
        out << (dict(id=i, modality_id=1, text=line.strip())
                for i, line in enumerate(f))

    with open('data/documents.mmro.txt') as f, \
            CsvWriter(ctx.obj.directory, 'document_terms') as out:
        out << (dict(document_id=d, modality_id=2, term_id=authors_terms[a]['id'], count=1)
                for d, a in doc_authors)
        out << (dict(document_id=d, modality_id=1, term_id=w, count=cnt)
                for d, line in enumerate(f)
                # count each word in line
                for w, cnt in Counter(int(dw.split()[0]) for dw in line.split(';')[:-1]).items())


@cli.command()
@click.pass_context
def topicmodel_basic(ctx):
    """
    Required topic model tables.
    """

    # load matrices and compute all the probabilities
    phi = sp.coo_matrix(np.load('data/phi.npy'))
    theta = sp.coo_matrix(np.load('data/theta.npy'))

    pwt = phi.A
    ptd = theta.A

    pd = 1.0 / theta.shape[1]
    pt = (ptd * pd).sum(1)
    pw = (pwt * pt).sum(1)
    ptw = pwt * pt / pw[:, np.newaxis]
    pdt = ptd * pd / pt[:, np.newaxis]

    with CsvWriter(ctx.obj.directory, 'topics') as out:
        out << [dict(id=0, type='foreground', probability=1)]  # the zero-level topic is required
        out << (dict(id=topic_id(1, t),
                     type='foreground' if t < 50 else 'background',
                     probability=p)
                for t, p in enumerate(pt))

    with CsvWriter(ctx.obj.directory, 'topic_terms') as out:
        out << (dict(topic_id=topic_id(1, t), modality_id=1, term_id=w, prob_wt=val, prob_tw=ptw[w, t])
                for w, t, val in zip(phi.row, phi.col, phi.data))

    with CsvWriter(ctx.obj.directory, 'document_topics') as out:
        out << (dict(topic_id=topic_id(1, t), document_id=d, prob_td=val, prob_dt=pdt[t, d])
                for t, d, val in zip(theta.row, theta.col, theta.data))

    with CsvWriter(ctx.obj.directory, 'topic_edges') as out:
        # all topics are assumed to be reachable by edges from the root topic #0
        out << (dict(parent_id=0, child_id=topic_id(1, t), probability=p)
                for t, p in enumerate(pt))


@cli.command()
@click.pass_context
def document_contents(ctx):
    """
    Optional tables: document highlighting.
    """
    with open('data/documents.mmro.txt') as f, \
            CsvWriter(ctx.obj.directory, 'document_contents') as out:
        id_cnt = it.count()
        out << (dict(id=next(id_cnt),  # must correspond to the ids in document_content_topics
                     document_id=d, modality_id=1, term_id=w,
                     start_pos=s, end_pos=e  # the start and end positions in the HTML content
                     )
                for d, line in enumerate(f)
                for w, s, e in (map(int, dw.split()) for dw in line.split(';')[:-1]))

    with open('data/ptdw.txt') as fp, \
            CsvWriter(ctx.obj.directory, 'document_content_topics') as out:
        id_cnt = it.count()
        out << (dict(document_content_id=next(id_cnt),  # same ids as above
                     topic_id=topic_id(1, int(t)))
                for d, linep in enumerate(fp)
                for t in linep.split())


if __name__ == '__main__':
    cli(obj=recordclass('Obj', 'directory')(directory=None))
