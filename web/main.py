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
        WordTuple = namedtuple('WordTuple', ['word', 'n', 'topics'])

        nw = h5f['n_wd'][...].sum(1).astype(int)
        indices = nw.argsort()[:-20-1:-1]
        nws = nw[indices]

        words = h5f['dictionary'][...][indices]

        pts = h5f['p_wt'][...][indices,:]
        topics = pts.argsort(axis=1)[:,:3]

    return render_template('words.html', words=starmap(WordTuple, zip(words, nws, topics)))


if __name__ == '__main__':
    app.run()
