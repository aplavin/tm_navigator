#!/usr/bin/env python2
import os, os.path, os
import h5py
import numpy as np
import scipy.sparse
from whoosh import index
import sys
sys.path.append('collection-processing')
import search
import unittest


class Tests(unittest.TestCase):

    def setUp(self):
        self.h5f = h5py.File(hdf5_file, mode='r')
        self.docs_ix = index.open_dir(whoosh_dir, readonly=True, indexname='docs')
        self.words_ix = index.open_dir(whoosh_dir, readonly=True, indexname='words')

    def test_all_tex_converted(self):
        for directory, subdirs, fnames in os.walk(texs_dir):
            # make paths relative to input directory
            assert directory.startswith(texs_dir)
            directory = directory[len(texs_dir):].strip('/')
            fnames = map(lambda name: os.path.join(directory, name), fnames)
            fnames = map(lambda name: os.path.splitext(name)[0], fnames)

            for fname in fnames:
                full = os.path.join(htmls_dir, fname + '.html')
                self.assertTrue(os.path.exists(full), full)
                self.assertGreater(os.path.getsize(full), 0, full)

    def test_almost_all_in_hdf(self):
        data_fnames = self.h5f['metadata']['filename']
        real_fnames = []

        for directory, subdirs, fnames in os.walk(htmls_dir):
            # make paths relative to input directory
            assert directory.startswith(htmls_dir)
            directory = directory[len(htmls_dir):].strip('/')
            fnames = map(lambda name: os.path.join(directory, name), fnames)
            fnames = filter(lambda name: os.path.splitext(name)[1] == '.html', fnames)
            fnames = map(lambda name: os.path.splitext(name)[0], fnames)
            real_fnames += fnames

        cnt_in = len(data_fnames)
        cnt_total = len(real_fnames)
        self.assertLessEqual(cnt_in, cnt_total)
        self.assertGreater(cnt_in, cnt_total / 2)

        self.assertSetEqual(set(data_fnames), set(data_fnames) & set(real_fnames))

    def test_slugs_unique(self):
        slugs = self.h5f['metadata']['slug']
        self.assertListEqual(sorted(slugs), sorted(set(slugs)))

    def test_words_unique(self):
        words = self.h5f['dictionary'][...]
        self.assertListEqual(sorted(words), sorted(set(words)))

    def test_dimensions_match(self):
        nwd_sp = self.h5f['n_wd_coo'][...]
        nwd_sp = scipy.sparse.coo_matrix((nwd_sp['data'], (nwd_sp['row'], nwd_sp['col'])))
        self.assertEqual(nwd_sp.shape, self.h5f['n_wd'].shape)
        self.assertEqual(self.h5f['n_wd'].shape[1], self.h5f['p_td'].shape[1])
        self.assertEqual(self.h5f['n_wd'].shape[0], self.h5f['p_wt'].shape[0])
        self.assertEqual(self.h5f['p_td'].shape[0], self.h5f['p_wt'].shape[1])
        self.assertEqual(self.h5f['n_wd'].shape[0], self.h5f['dictionary'].shape[0])
        self.assertEqual(self.h5f['n_wd'].shape[1], self.h5f['metadata'].shape[0])

    def test_existant_words_used(self):
        ws_cnt = self.h5f['dictionary'].shape[0]
        ws_used = set()
        for d, doc in self.h5f['documents'].items():
            ws_used.update(doc['w'])
        self.assertSetEqual(ws_used, set(range(ws_cnt)))

    def test_word_positions_ok(self):
        for d, doc in self.h5f['documents'].items():
            poses = doc['startpos', 'endpos']
            self.assertTrue((poses['startpos'][1:] > poses['endpos'][:-1]).all(), 'd: %s' % d)
            self.assertTrue((poses['endpos'] > poses['startpos']).all(), 'd: %s' % d)

    def test_existant_topics_used(self):
        ts_cnt = self.h5f['p_td'].shape[0]
        ts_used = set()
        for d, doc in self.h5f['documents'].items():
            ts_used.update(doc.attrs['topics'])
            ts_used.update(doc['topics'].flatten())
        self.assertSetEqual(ts_used, set(range(ts_cnt)))

    def test_existant_docs_used(self):
        ds_cnt = self.h5f['n_wd'].shape[1]
        ds_used = map(int, self.h5f['documents'])
        self.assertListEqual(sorted(ds_used), range(ds_cnt))

    def test_matrices_correctness(self):
        nwd_sp = self.h5f['n_wd_coo'][...]
        nwd_sp = scipy.sparse.coo_matrix((nwd_sp['data'], (nwd_sp['row'], nwd_sp['col'])))
        self.assertTrue((self.h5f['n_wd'][...] == nwd_sp.A).all())
        self.assertTrue((self.h5f['n_wd'][...] >= 0).all())
        self.assertTrue((self.h5f['n_wd'][...].sum(0) > 0).all())
        self.assertTrue((self.h5f['n_wd'][...].sum(1) > 0).all())

        self.assertTrue((self.h5f['p_wt'][...] >= 0).all())
        self.assertTrue(np.allclose(self.h5f['p_wt'][...].sum(0), 1))
        self.assertTrue((self.h5f['p_wt'][...].sum(1) > 0).all())

        self.assertTrue((self.h5f['p_td'][...] >= 0).all())
        self.assertTrue(np.allclose(self.h5f['p_td'][...].sum(0), 1))
        self.assertTrue((self.h5f['p_td'][...].sum(1) > 0).all())

    def test_words_in_docs_match_nwd(self):
        nwd = self.h5f['n_wd'][...]
        for d, doc in self.h5f['documents'].items():
            cnts = np.bincount(doc['w'], minlength=nwd.shape[0])
            self.assertTrue((nwd[:, int(d)] == cnts).all())

    def test_index_consistency(self):
        self.assertEqual(self.h5f['n_wd'].shape[1], self.docs_ix.doc_count_all())
        self.assertEqual(self.h5f['n_wd'].shape[0], self.words_ix.doc_count_all())

        with self.docs_ix.searcher() as searcher:
            self.assertSetEqual(set(searcher.field_terms('slug')), set(self.h5f['metadata']['slug']))
            self.assertSetEqual(set(searcher.field_terms('fname')), set(self.h5f['metadata']['filename']))

        with self.words_ix.searcher() as searcher:
            self.assertSetEqual(set(filter(lambda w: w >= 0, searcher.field_terms('w'))), set(range(self.h5f['n_wd'].shape[0])))


texs_dir = 'documents/tex'
htmls_dir = 'web/static/docsdata'
hdf5_file = 'data.hdf'
whoosh_dir = 'whoosh_ix'
# texs_dir = 'documents/tex'
# htmls_dir = 'collection-processing/html'
# hdf5_file = 'collection-processing/data.hdf5'
# whoosh_dir = 'collection-processing/whoosh_ix'

unittest.main(verbosity=2)
