#!/usr/bin/env python2
import argparse
import codecs
import logging
import numpy as np
import scipy.sparse
import os, os.path
import sys
import h5py
import re
from ipy_progressbar import ProgressBar
from html_parser import MyHTMLParser


logging.basicConfig(format='%(levelname)s: %(message)s')


# parsing command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('input', help='input directory with HTML files')
parser.add_argument('output', help='output HDF5 file')
parser.add_argument('--nwd-only', action='store_true', help='compute and output only N_wd matrix; if not given, the output HDF5 file must contain matrices p_wt and p_td.')
args = parser.parse_args()


# find files in input directory
files = []
for directory, subdirs, fnames in os.walk(args.input):
    fnames = map(lambda name: os.path.join(directory, name), fnames)
    files += fnames

htmlfiles = [f for f in files if os.path.splitext(f)[1].lower() == '.html']
if files != htmlfiles:
    logging.warning('%d files in the input directory have extension different from .html, ignoring them', len(files) - len(htmlfiles))
    files = htmlfiles

if not files:
    logging.error('no HTML files to process - stopping now')
    sys.exit()


# get words from HTML files
docs = []

for fname in ProgressBar(files, title='Parse HTML'):
    with codecs.open(fname, encoding='utf-8') as f:
        html = f.read()

        parser = MyHTMLParser(html)
        doc_content = np.array(parser.words, dtype=[('word', h5py.special_dtype(vlen=unicode)),
                                                    ('wnorm', h5py.special_dtype(vlen=unicode)),
                                                    ('start', np.int32),
                                                    ('end', np.int32)])

        if 1.0 * parser.cntlatin / (parser.cntlatin + len(doc_content)) > 0.5:
            # MMRO/IOI collection has several english docs - drop them
            continue
        docs.append((fname, parser.metadata, doc_content))


# build a single list of normalized words
wnorms = np.concatenate([dc[2]['wnorm'] for dc in docs])
wnorms = np.unique(wnorms)
dictionary = wnorms.astype(h5py.special_dtype(vlen=unicode))
# and a dict with their indices for lookup
wnorms_dict = {wnorm: w for w, wnorm in enumerate(wnorms)}


# replace normalized words with their indices in documents
new_docs = []
for fname, meta, content in ProgressBar(docs, title='Get word indices'):
    new_content = np.empty((len(content),), dtype=[('word', h5py.special_dtype(vlen=unicode)),
                                                  ('w', np.int32),
                                                  ('start', np.int32),
                                                  ('end', np.int32)])
    new_content['word'] = content['word']
    new_content['start'] = content['start']
    new_content['end'] = content['end']
    new_content['w'] = [wnorms_dict[wnorm] for wnorm in content['wnorm'].astype('U')]

    new_docs.append((fname, meta, new_content))

docs = new_docs


if args.nwd_only:
    # build N_wd matrix
    nwd = np.zeros((len(dictionary), len(docs)), dtype=np.int32)
    for d, (_, _, content) in enumerate(ProgressBar(docs, title='Build N_wd')):
        for w in content['w']:
            nwd[w, d] += 1

    # and make it sparse
    # TODO: build sparse from beginning
    nwd_sp = scipy.sparse.coo_matrix(nwd)
    nwd_sp_arr = np.array(map(tuple, np.vstack([nwd_sp.data, nwd_sp.col, nwd_sp.row]).T),
                          dtype=[('data', np.int32),
                                 ('col', np.int32),
                                 ('row', np.int32)])

    with h5py.File(args.output, mode='w') as f:
        f.create_dataset('n_wd_coo', data=nwd_sp_arr, compression='gzip')
        f.create_dataset('n_wd', data=nwd, compression='gzip')
    sys.exit()


# get metadata for each document
metadata = []
slugs_seens = set()
for fname, meta, cont in ProgressBar(docs, title='Get metadata'):
    fname = fname[len(args.input):].strip('/').replace('.html', '')

    year, conference = fname.split('/')[-2].split('-')
    conference, confnum = re.match(r'^(\D+)(\d+)$', conference).groups()
    year = int(year)
    confnum = int(confnum)

    author_fws = re.findall(r'\w{3,}', meta['author'], re.U)
    title_fws = re.findall(r'\w{3,}', meta['title'], re.U)

    slug = None
    # generate unique slugs
    while not slug or slug in slugs_seens:
        author_fw = author_fws[0]
        title_fw = title_fws.pop(0)
        slug = author_fw + str(year)[2:] + title_fw
        slug = slug.lower()
    assert slug not in slugs_seens
    slugs_seens.add(slug)

    metadata.append((fname, meta['title'], meta['author'], slug, conference, confnum, year))

metadata = np.array(metadata, dtype=[('filename', h5py.special_dtype(vlen=unicode)),
                                     ('title', h5py.special_dtype(vlen=unicode)),
                                     ('authors', h5py.special_dtype(vlen=unicode)),
                                     ('slug', h5py.special_dtype(vlen=unicode)),
                                     ('conference', h5py.special_dtype(vlen=unicode)),
                                     ('confnum', np.int32),
                                     ('year', np.int32)])


# load Phi and Theta
with h5py.File(args.output, mode='r') as h5f:
    pwt = h5f['p_wt'][...]
    ptd = h5f['p_td'][...]


# generate document contents with each word topics probabilities
docs_contents = []

for d, (_, _, content) in enumerate(ProgressBar(docs, title='Word probabilities')):
    pwts = pwt * ptd[:, d].T
    pwts /= pwts.sum(1)[:,np.newaxis]
    pwts[np.isnan(pwts.sum(1)), :] = 0

    topics_glob = ptd[:,d].argsort()[::-1][:np.count_nonzero(ptd[:,d])]
    doc_content = []

    for word, w, start, end in content:
        pts = pwts[w]
        topics = pts.argsort()[::-1][:5]
        pts_glob = pts[topics_glob]
        pts = pts[topics]

        doc_content.append((w, start, end, topics, pts, pts_glob))

    docs_contents.append((topics_glob,
                         np.array(doc_content,
                                 dtype=[('w', np.int32),
                                        ('startpos', np.int32),
                                        ('endpos', np.int32),
                                        ('topics', np.int32, 5),
                                        ('pts', np.float32, 5),
                                        ('pts_glob', np.float32, len(topics_glob))])))


# save to the hdf file
with h5py.File(args.output, mode='a') as f:
    f.create_dataset('dictionary', data=dictionary, compression='gzip')
    f.create_dataset('metadata', data=metadata, compression='gzip')

    docs_group = f.create_group('documents')
    for i, (topics, doc) in enumerate(docs_contents):
        dset = docs_group.create_dataset('%d' % i, data=doc, compression='gzip')
        dset.attrs['topics'] = topics
