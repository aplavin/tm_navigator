import numpy as np
import scipy.sparse
from scipy.ndimage.filters import convolve1d
from itertools import starmap
from collections import Counter
from recordtype import recordtype
import h5py
import codecs
import re


h5f = h5py.File('../data.hdf', mode='r')


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


def get_words_all():
    nws = get_nwd(h5f).sum(1).A1
    ws = nws.argsort()[::-1]
    words = h5f['dictionary'][...][ws]
    words = list( starmap(WordTuple, zip(ws, nws[ws], words)) )
    return words


def get_documents_all():
    nds = get_nwd(h5f).sum(0).A1
    ds = nds.argsort()[::-1]
    meta = h5f['metadata'][...][ds]
    docs = list( starmap(DocumentTuple, zip(ds, nds[ds], meta)) )
    return docs


def get_topics_all():
    nds = get_nwd(h5f).sum(0).A1
    ptds = h5f['p_td'][...]
    pts = ptds.dot(1.0 * nds / nds.sum())
    ts = pts.argsort()[::-1]
    topics = list( starmap(TopicTuple, zip(ts, pts[ts])) )
    return topics


def get_topics_info(ts, ntop=(-1, -1)):
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


def d_by_slug(slug):
    slugs = h5f['metadata']['slug']
    d = np.nonzero(slugs == slug)[0][0]
    return d


def get_docs_info(ds, ntop=(-1, -1)):
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


def get_doc_content(doc):
    content = h5f['documents'][str(doc.d)][...]

    filename = h5f['metadata']['filename', doc.d]
    with codecs.open('static/docsdata/%s.html' % filename, encoding='utf-8') as f:
        html = f.read()

    topics_used = Counter()
    html_new = ''
    html_pos = 0
    for w, start, end, _, _, pts_glob in content:
        topic = doc.topics[pts_glob.argmax()]
        topics_used[topic.t] += 1

        html_new += html[html_pos:start]
        html_new += '<span data-word="%d" data-color="%d"><a href="#">' % (w, topic.t)
        html_new += html[start:end]
        html_new += '</a></span>'
        html_pos = end
    html_new += html[end:]

    html = re.search(r'</header>(.*)</body>', html_new, re.DOTALL).group(1)

    html = re.sub(r'<img class="(\w+)" src="\w+/(eqn\d+).png".*?/>',
                  r'<span class="sprite-\2"></span>',
                  html, flags=re.DOTALL | re.MULTILINE)

    topics_in_content = [TopicTuple(t.t, (t.np, topics_used[t.t]))
                         for t in doc.topics
                         if t.t in topics_used]
    doc.topics = [t
                  for t in doc.topics
                  if t.t in topics_used]

    # generate smooth topics flow
    topics_flow = content['pts_glob']
    if topics_flow.ndim == 1:
        topics_flow = topics_flow[:, np.newaxis]
    wlen = 100
    window = np.bartlett(wlen)
    topics_flow = convolve1d(topics_flow, window / window.sum(), axis=0)
    topics_flow = list( starmap(TopicTuple, zip( [t.t for t in doc.topics], zip(*map(tuple, topics_flow)) )) )

    return {
        'html': html,
        'topics_in_content': topics_in_content,
        'topics_flow': topics_flow
    }


def w_by_word(word):
    words = h5f['dictionary'][...]
    w = np.nonzero(words == word)[0][0]
    return w


def get_words_info(ws, ntop=(-1, -1)):
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
