from flask import Flask, render_template
import h5py
from recordtype import recordtype
from itertools import starmap, groupby
from collections import Counter
from math import isnan


app = Flask(__name__)

WordTuple = recordtype('WordTuple', ['w', 'np', 'word', 'topics', 'documents'], default=None)
ContentWordTuple = recordtype('ContentWordTuple', ['w', 'np', 'word', 'word_norm', 'topics'], default=None)
TopicTuple = recordtype('TopicTuple', ['t', 'np', 'documents', 'words'], default=None)
DocumentTuple = recordtype('DocumentTuple', ['d', 'np', 'name', 'topics', 'words', 'content'], default=None)


@app.route('/')
def overview():
    return render_template('overview.html')


@app.route('/words')
def words():
    with h5py.File('../data.hdf', mode='r') as h5f:
        nw = h5f['n_wd'][...].sum(1)
        indices = nw.argsort()[:-21:-1]

        words = [get_word_info(w, h5f, 5) for w in indices]

    return render_template('words.html', words=words)


@app.route('/documents')
def documents():
    with h5py.File('../data.hdf', mode='r') as h5f:
        nw = h5f['n_wd'][...].sum(0)
        indices = nw.argsort()[:-21:-1]

        docs = [get_doc_info(d, h5f, 5) for d in indices]

    return render_template('documents.html', docs=docs)


@app.route('/topics')
def topics():
    with h5py.File('../data.hdf', mode='r') as h5f:        
        ptds = h5f['p_td'][...]
        nds = h5f['n_wd'][...].sum(0)
        pts = ptds.dot(1.0 * nds / nds.sum())
        indices = pts.argsort()[:-21:-1]

        topics = [get_topic_info(t, h5f, 5) for t in indices]

    return render_template('topics.html', topics=topics)


@app.route('/word/<int:w>')
def word(w):
    with h5py.File('../data.hdf', mode='r') as h5f:
        word = get_word_info(w, h5f)

    return render_template('word.html', word=word)


def get_word_info(w, h5f, ntop=-1):
    nw = h5f['n_wd'][...].sum(1)[w]
    word = h5f['dictionary'][...][w]

    pts = h5f['p_wt'][...][w,:]
    topics = pts.argsort()[::-1]
    if ntop >= 0:
        topics = topics[:ntop]
    topics = list( starmap(TopicTuple, zip(topics, pts[topics])) )
    topics = filter(lambda t: t.np > 0, topics)

    nds = h5f['n_wd'][...][w,:]
    docs = nds.argsort()[::-1]
    if ntop >= 0:
        docs = docs[:ntop]
    docs = list( starmap(DocumentTuple, zip(docs, nds[docs])) )
    docs = filter(lambda d: d.np > 0, docs)

    return WordTuple(w, nw, word, topics, docs)


@app.route('/topic/<int:t>')
def topic(t):
    with h5py.File('../data.hdf', mode='r') as h5f:
        topic = get_topic_info(t, h5f)

    return render_template('topic.html', topic=topic)


def get_topic_info(t, h5f, ntop=-1):
    pds = h5f['p_td'][...][t,:]
    nds = h5f['n_wd'][...].sum(0)
    pt = pds.dot(1.0 * nds / nds.sum())

    pws = h5f['p_wt'][...][:,t]
    ws = pws.argsort()[::-1]
    if ntop >= 0:
        ws = ws[:ntop]
    words = h5f['dictionary'][...][ws]
    words = list( starmap(WordTuple, zip(ws, pws[ws], words)) )
    words = filter(lambda w: w.np > 0, words)

    docs = pds.argsort()[::-1]
    if ntop >= 0:
        docs = docs[:ntop]
    docs = list( starmap(DocumentTuple, zip(docs, pds[docs])) )
    docs = filter(lambda d: d.np > 0, docs)

    return TopicTuple(t, pt, docs, words)


@app.route('/document/<int:d>')
def document(d):
    with h5py.File('../data.hdf', mode='r') as h5f:
        doc = get_doc_info(d, h5f)

        content = h5f['documents'][str(d)][...]

        ws = content['w']
        words_norm = h5f['dictionary'][...][ws]
        nws = h5f['n_wd'][...][ws, d]

        words = content['word']
        wtopics = [TopicTuple(ts[0], ps[0])
                   for ts, ps in zip(content['topics'], content['pts'])]

        topics = groupby(sorted((t
                                 for t in wtopics
                                 if not isnan(t.np)),
                                key=lambda t: t.t),
                         key=lambda t: t.t)
        topics = [(tt, sum(t.np for t in items))
                  for tt, items in topics]
        topics.sort(key=lambda (tt, np): np, reverse=True)


        doc.content = list( starmap(ContentWordTuple, zip(ws, nws, words, words_norm, wtopics)) )

    return render_template('document.html', doc=doc, topics=topics)


def get_doc_info(d, h5f, ntop=-1):
    name = h5f['docinfo'][...][d][1]
    nd = h5f['n_wd'][...].sum(0)[d]

    pts = h5f['p_td'][...][:,d]
    topics = pts.argsort()[::-1]
    if ntop >= 0:
        topics = topics[:ntop]
    topics = list( starmap(TopicTuple, zip(topics, pts[topics])) )
    topics = filter(lambda t: t.np > 0, topics)

    nws = h5f['n_wd'][...][:,d]
    ws = nws.argsort()[::-1]
    if ntop >= 0:
        ws = ws[:ntop]
    words = h5f['dictionary'][...][ws]
    words = list( starmap(WordTuple, zip(ws, nws[ws], words)) )
    words = filter(lambda w: w.np > 0, words)

    return DocumentTuple(d, nd, name, topics, words)


if __name__ == '__main__':
    app.run(debug=True)
