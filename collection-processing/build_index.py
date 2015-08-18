#!/usr/bin/env python2
import argparse
import codecs
import logging
import os, os.path
import sys
import h5py
import scipy.sparse
import re
from whoosh import fields, analysis, index
from search import WithFloatData, RemoveDuplicatesFilter
from ipy_progressbar import ProgressBar


logging.basicConfig(format='%(levelname)s: %(message)s')


# parsing command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('input', help='input directory with HTML files')
parser.add_argument('hdf5', help='input HDF5 file')
parser.add_argument('output', help='output directory for whoosh search index')
args = parser.parse_args()


# check output directory
if not os.path.isdir(args.output) or os.listdir(args.output):
    logging.error('output directory does not exist or is not empty - stopping now')
    sys.exit()


# declare schemas
analyzer = (analysis.RegexTokenizer(r'\S+') |
            analysis.MultiFilter(index=analysis.IntraWordFilter(mergewords=True, mergenums=True), query=analysis.IntraWordFilter()) |
            analysis.SubstitutionFilter(r'^\W+', '') |
            analysis.SubstitutionFilter(r'\W+$', '') |
            analysis.StopFilter(lang='ru') |
            analysis.TeeFilter(analysis.PassFilter(),
                               analysis.LowercaseFilter(),
                               analysis.StemFilter(lang='ru')) |
            analysis.StopFilter(stoplist=set()) |
            RemoveDuplicatesFilter())

topics_field = fields.FieldType(WithFloatData(),
                                analyzer=analysis.IDAnalyzer(),
                                stored=False,
                                scorable=True,
                                vector=WithFloatData())

docs_schema = fields.Schema(d=fields.NUMERIC(stored=True, unique=True),
                           fname=fields.ID(stored=True, unique=True),
                           slug=fields.ID(stored=True, unique=True),
                           topics=topics_field,
                           content=fields.TEXT(stored=False, spelling=True, phrase=True, chars=True, analyzer=analyzer),
                           title=fields.TEXT(stored=True, spelling=True, analyzer=analyzer, field_boost=3.0),
                           authors=fields.TEXT(stored=True, spelling=True, field_boost=2.0),
                           conference=fields.ID(stored=True),
                           year=fields.NUMERIC(stored=True),

                           title_ngrams=fields.NGRAMWORDS(stored=True, field_boost=2.0),
                           authors_ngrams=fields.NGRAMWORDS(stored=True, field_boost=2.0),
                           authors_tags=fields.KEYWORD(stored=True, commas=True, scorable=True, vector=True))

words_schema = fields.Schema(w=fields.NUMERIC(stored=True, unique=True),
                             n=fields.NUMERIC(stored=True),
                             word=fields.TEXT(stored=True, spelling=True, analyzer=analyzer),
                             word_ngrams=fields.NGRAM(stored=True))


# create indices
docs_ix = index.create_in(args.output, docs_schema, 'docs')
words_ix = index.create_in(args.output, words_schema, 'words')


# build docs index
with docs_ix.writer() as writer, h5py.File(args.hdf5, mode='r') as h5f:
    ptd = h5f['p_td'][...]

    for d, (fname, title, authors, slug, conf, _, year) in enumerate(ProgressBar(h5f['metadata'][...], title='Docs index')):
        # get content as plain text
        with codecs.open(os.path.join(args.input, fname + '.html'), encoding='utf-8') as f:
            html = f.read()
            m = re.search(r'</header>(.*)</body>', html, re.DOTALL)
            if m is None:
                print(fname)
                continue
            html = m.group(1)
            content = re.sub('<[^<]+?>', ' ', html)

        # sorted topics
        topics = ptd[:,d].argsort()[::-1]
        topics = [(unicode(t), p)
                  for t, p in zip(topics, ptd[topics,d])
                  if p > 0]
        topics.sort(key=lambda t: t[1], reverse=True)

        data = {
            'd': d,
            'fname': unicode(fname),
            'slug': unicode(slug),
            'content': unicode(content),
            'title': unicode(title),
            'authors': unicode(authors),
            'conference': unicode(conf),
            'year': year,
            'topics': topics,
        }
        docdata = {name: data[name.split('_')[0]]
                   for name in docs_schema.names()}
        writer.add_document(**docdata)

    logging.info('Finalizing docs index...')


# build words index
with words_ix.writer() as writer, h5py.File(args.hdf5, mode='r') as h5f:
    pwt = h5f['p_wt'][...]
    if 'n_wd_coo' in h5f:
        nwd = h5f['n_wd_coo'][...]
        nwd = scipy.sparse.coo_matrix((nwd['data'], (nwd['row'], nwd['col'])))
        nw = nwd.sum(1).A1
    else:
        nwd = h5f['n_wd'][...]
        nw = nwd.sum(1)

    words_all = h5f['dictionary'][...]

    for w, (word, n, pt) in enumerate(ProgressBar(zip(words_all, nw, pwt), title='Words index')):
        data = {
            'w': w,
            'n': n,
            'word': word,
        }
        docdata = {name: data[name.split('_')[0]]
                   for name in words_schema.names()}
        writer.add_document(**docdata)


    logging.info('Finalizing words index...')
