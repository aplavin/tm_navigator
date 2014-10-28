#!/usr/bin/env python2
import h5py
import argparse
import logging
import numpy as np
import scipy.sparse
import sys
import py_artm


logging.basicConfig(format='%(levelname)s: %(message)s')


# parsing command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('hdf5', help='HDF5 file with n_wd (dense) or n_wd_coo (sparse; preferred if both exist) matrix. Resulting matrices p_wt and p_td are saved to it also.')
args = parser.parse_args()


with h5py.File(args.hdf5, mode='r') as f:
    if 'n_wd_coo' in f:
        nwd_sp = f['n_wd_coo'][...]
        nwd_sp = scipy.sparse.coo_matrix((nwd_sp['data'], (nwd_sp['row'], nwd_sp['col'])))
        nwd_sp = nwd_sp.astype(np.float32)
    if 'n_wd' in f:
        nwd = f['n_wd'][...]
        nwd = nwd.astype(np.float32)
    if 'n_wd_coo' not in f and 'n_wd' in f:
        logging.error('neither n_wd_coo nor n_wd matrix is found in the HDF5 file')
        sys.exit()

try:
    em = py_artm.plsa.PlsaEmRational(nwd_sp,
                                     50, # number of topics
                                     []) # different regularizers and quantities to compute - optional
    em.iterate(500, # number of iterations
               quiet=1)
except:
    em = py_artm.plsa.PlsaEmRational(nwd,
                                     50, # number of topics
                                     []) # different regularizers and quantities to compute - optional
    em.iterate(500, # number of iterations
               quiet=1)


with h5py.File(args.hdf5, mode='a') as f:
    f.create_dataset('p_wt', data=em.phi, compression='gzip')
    f.create_dataset('p_td', data=em.theta, compression='gzip')
