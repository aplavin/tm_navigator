from flask import Flask, render_template
import h5py
from collections import namedtuple
from itertools import starmap


app = Flask(__name__)


@app.route('/')
def overview():
    return render_template('overview.html')


@app.route('/words')
def words():
    with h5py.File('../data.hdf', mode='r') as h5f:
        WordTuple = namedtuple('WordTuple', ['w', 'word', 'n', 'topics'])
        TopicTuple = namedtuple('TopicTuple', ['t', 'p'])

        nw = h5f['n_wd'][...].sum(1)
        indices = nw.argsort()[:-20-1:-1]
        nws = nw[indices]

        words = h5f['dictionary'][...][indices]

        pts = h5f['p_wt'][...][indices,:]
        topics = []
        for w_pts in pts:
            w_topics = w_pts.argsort()[:-4:-1]
            topics.append(list( starmap(TopicTuple, zip(w_topics, w_pts[w_topics])) ))

    return render_template('words.html', words=starmap(WordTuple, zip(indices, words, nws, topics)))


@app.route('/word/<int:w>')
def word(w):
    WordTuple = namedtuple('WordTuple', ['w', 'word', 'n', 'topics', 'documents'])
    TopicTuple = namedtuple('TopicTuple', ['t', 'p'])
    DocumentTuple = namedtuple('DocumentTuple', ['d', 'n'])

    ntop = 0
    with h5py.File('../data.hdf', mode='r') as h5f:
        nw = h5f['n_wd'][...].sum(1)[w]
        word = h5f['dictionary'][...][w]

        pts = h5f['p_wt'][...][w,:]
        topics = pts.argsort()[::-1]
        if ntop > 0:
            topics = topics[:ntop]
        topics = list( starmap(TopicTuple, zip(topics, pts[topics])) )

        nds = h5f['n_wd'][...][w,:]
        docs = nds.argsort()[::-1]
        if ntop > 0:
            docs = docs[:ntop]
        docs = list( starmap(DocumentTuple, zip(docs, nds[docs])) )

    return render_template('word.html', word=WordTuple(w, word, nw, topics, docs))


@app.route('/topic/<int:t>')
def topic(t):
    pass


@app.route('/document/<int:d>')
def document(t):
    pass


if __name__ == '__main__':
    app.run(debug=True)
