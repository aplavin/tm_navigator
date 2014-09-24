import numpy as np
import scipy.sparse
from itertools import starmap
from recordtype import recordtype


def zipnp(*arrs):
    def castarr(arr):
        if isinstance(arr, list):
            return arr
        elif np.issubdtype(arr.dtype, np.integer):
            assert arr.ndim == 1
            return map(int, arr)
        elif np.issubdtype(arr.dtype, np.float):
            assert arr.ndim == 1
            return map(float, arr)
        else:
            return arr
    lsts = map(castarr, arrs)
    return zip(*lsts)


def get_nwd(h5f):
    arr = h5f['n_wd_coo'][...]
    return scipy.sparse.coo_matrix((arr['data'], (arr['row'], arr['col'])))


WordTuple = recordtype('WordTuple', ['w', 'np', 'word', 'topics', 'documents'], default=None)
ContentWordTuple = recordtype('ContentWordTuple', ['w', 'np', 'word', 'word_norm', 'topics'], default=None)
TopicTuple = recordtype('TopicTuple', ['t', 'np', 'documents', 'words'], default=None)
DocumentTuple = recordtype('DocumentTuple', ['d', 'np', 'meta', 'topics', 'words', 'content'], default=None)


def get_topics_info(ts, h5f, ntop=(-1, -1)):
    pds = h5f['p_td'][...][ts,:]
    nds = get_nwd(h5f).sum(0).A1
    pt = pds.dot(1.0 * nds / nds.sum())

    pws = h5f['p_wt'][...][:,ts].T
    ws = pws.argsort(axis=1)[:,::-1]
    if ntop[1] >= 0:
        ws = ws[:,:ntop[1]]
    words = h5f['dictionary'][...][ws]
    words = [list( starmap(WordTuple, zipnp(ws_r, pws_r[ws_r], words_r)) )
             for ws_r, pws_r, words_r in zip(ws, pws, words)]
    words = map(
        lambda words_r: filter(lambda w: w.np > 0, words_r),
        words)

    docs = pds.argsort(axis=1)[:, ::-1]
    if ntop[0] >= 0:
        docs = docs[:, :ntop[0]]
    docsmeta = h5f['metadata'][...][docs]
    docs = [list( starmap(DocumentTuple, zipnp(docs_r, pds_r[docs_r], meta_r)) )
            for docs_r, pds_r, meta_r in zip(docs, pds, docsmeta)]
    docs = map(
        lambda docs_r: filter(lambda d: d.np > 0, docs_r),
        docs)

    return list( starmap(TopicTuple, zip(ts, pt, docs, words)) )


def get_docs_info(ds, h5f, ntop=(-1, -1)):
    meta = h5f['metadata'][...][ds]
    nd = get_nwd(h5f).sum(0).A1[ds]

    pts = h5f['p_td'][...][:,ds].T
    topics = pts.argsort(axis=1)[:,::-1]
    if ntop[0] >= 0:
        topics = topics[:,:ntop[0]]
    topics = [list( starmap(TopicTuple, zipnp(topics_r, pts_r[topics_r])) )
              for topics_r, pts_r in zip(topics, pts)]
    topics = map(
        lambda topics_r: filter(lambda t: t.np > 0, topics_r),
        topics)

    nws = get_nwd(h5f).tocsc()[:,ds].A.T
    ws = nws.argsort()[:, ::-1]
    if ntop[1] >= 0:
        ws = ws[:,:ntop[1]]
    words = h5f['dictionary'][...][ws]
    words = [list( starmap(WordTuple, zipnp(ws_r, nws_r[ws_r], words_r)) )
             for ws_r, nws_r, words_r in zip(ws, nws, words)]
    words = map(
        lambda words_r: filter(lambda w: w.np > 0, words_r),
        words)

    return list( starmap(DocumentTuple, zipnp(ds, nd, meta, topics, words)) )


def get_words_info(ws, h5f, ntop=(-1, -1)):
    nw = get_nwd(h5f).sum(1).A1[ws]
    word = h5f['dictionary'][...][ws]

    pts = h5f['p_wt'][...][ws,:]
    topics = pts.argsort(axis=1)[:,::-1]
    if ntop[0] >= 0:
        topics = topics[:,:ntop[0]]
    topics = [list( starmap(TopicTuple, zipnp(topics_r, pts_r[topics_r])) )
              for topics_r, pts_r in zip(topics, pts)]
    topics = map(
        lambda topics_r: filter(lambda t: t.np > 0, topics_r),
        topics)

    nds = get_nwd(h5f).tocsr()[ws,:].A
    docs = nds.argsort(axis=1)[:,::-1]
    if ntop[1] >= 0:
        docs = docs[:,:ntop[1]]
    docsmeta = h5f['metadata'][...][docs]
    docs = [list( starmap(DocumentTuple, zipnp(docs_r, nds_r[docs_r], meta_r)) )
            for docs_r, nds_r, meta_r in zip(docs, nds, docsmeta)]
    docs = map(
        lambda docs_r: filter(lambda d: d.np > 0, docs_r),
        docs)

    return list( starmap(WordTuple, zipnp(ws, nw, word, topics, docs)) )
