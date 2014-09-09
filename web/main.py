from flask import Flask, render_template
import h5py
from collections import namedtuple
from itertools import starmap


app = Flask(__name__)

WordTuple = namedtuple('WordTuple', ['w', 'word', 'n', 'topics', 'documents'])
TopicTuple = namedtuple('TopicTuple', ['t', 'p'])
DocumentTuple = namedtuple('DocumentTuple', ['d', 'n'])


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


@app.route('/word/<int:w>')
def word(w):
    with h5py.File('../data.hdf', mode='r') as h5f:
        word = get_word_info(w, h5f, ntop=0)

    return render_template('word.html', word=word)


def get_word_info(w, h5f, ntop):
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

    return WordTuple(w, word, nw, topics, docs)


@app.route('/topic/<int:t>')
def topic(t):
    pass


@app.route('/document/<int:d>')
def document(t):
    pass


if __name__ == '__main__':
    app.run(debug=True)
