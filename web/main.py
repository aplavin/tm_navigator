from flask import Flask, render_template
from flask.ext.assets import Environment
from flask_debugtoolbar import DebugToolbarExtension
from flask_debugtoolbar_lineprofilerpanel.profile import line_profile
import h5py
from recordtype import recordtype
from itertools import starmap, groupby
from math import isnan
import numpy as np
from scipy.ndimage.filters import convolve1d
import codecs
import re
import inspect
import sys
import subprocess
import datetime


app = Flask(__name__)
assets = Environment(app)
app.debug = True
app.config.update({
    'SECRET_KEY': '\xcby\x01V\xff\x80\xf5\xb0I]\xa5\x84:\xd8\xfd\x87 \xc5\xa49\x05\x92\xa7\xafP\x87\x1b\xfe\xa8\x03\x84\xad',
    'DEBUG_TB_PANELS': [
        'flask_debugtoolbar.panels.versions.VersionDebugPanel',
        'flask_debugtoolbar.panels.timer.TimerDebugPanel',
        'flask_debugtoolbar.panels.headers.HeaderDebugPanel',
        'flask_debugtoolbar.panels.request_vars.RequestVarsDebugPanel',
        'flask_debugtoolbar.panels.template.TemplateDebugPanel',
        'flask_debugtoolbar.panels.logger.LoggingPanel',
        'flask_debugtoolbar.panels.profiler.ProfilerDebugPanel',

        'flask_debugtoolbar_lineprofilerpanel.panels.LineProfilerPanel'
    ],
    'DEBUG_TB_PROFILER_ENABLED': True,
    'DEBUG_TB_TEMPLATE_EDITOR_ENABLED': True,
})
toolbar = DebugToolbarExtension(app)

def debug():
    assert app.debug == False, "Don't panic! You're here by request of debug()"

out = subprocess.check_output("find .. -type f -print0 | xargs -0 stat --format '%Y :%y %n' | sort -nr | cut -d' ' -f2,3 | cut -d. -f1 | sed 's/://' | head -1", shell=True)
last_updated = datetime.datetime.strptime(out, '%Y-%m-%d %H:%M:%S\n')


@app.context_processor
def inject_last_updated():
    return dict(last_updated=last_updated)


WordTuple = recordtype('WordTuple', ['w', 'np', 'word', 'topics', 'documents'], default=None)
ContentWordTuple = recordtype('ContentWordTuple', ['w', 'np', 'word', 'word_norm', 'topics'], default=None)
TopicTuple = recordtype('TopicTuple', ['t', 'np', 'documents', 'words'], default=None)
DocumentTuple = recordtype('DocumentTuple', ['d', 'np', 'name', 'topics', 'words', 'content'], default=None)


@app.route('/')
def overview():
    with h5py.File('../data.hdf', mode='r') as h5f:
        nws = h5f['n_wd'][...].sum(1)
        ws = nws.argsort()[::-1]
        words = h5f['dictionary'][...][ws]
        words = list( starmap(WordTuple, zip(ws, nws[ws], words)) )

        nds = h5f['n_wd'][...].sum(0)
        ds = nds.argsort()[::-1]
        docs = list( starmap(DocumentTuple, zip(ds, nds[ds])) )

        ptds = h5f['p_td'][...]
        pts = ptds.dot(1.0 * nds / nds.sum())
        ts = pts.argsort()[::-1]
        topics = list( starmap(TopicTuple, zip(ts, pts[ts])) )

    return render_template('overview.html', words=words[:100], docs=docs[:100], topics=topics)


@app.route('/topics')
def topics():
    with h5py.File('../data.hdf', mode='r') as h5f:
        ptds = h5f['p_td'][...]
        nds = h5f['n_wd'][...].sum(0)
        pts = ptds.dot(1.0 * nds / nds.sum())
        indices = pts.argsort()[::-1]

        topics = get_topics_info(indices, h5f, 30)

    return render_template('topics.html', topics=topics)


@app.route('/documents')
def documents():
    with h5py.File('../data.hdf', mode='r') as h5f:
        nw = h5f['n_wd'][...].sum(0)
        indices = nw.argsort()[::-1]

        docs = get_docs_info(indices, h5f, 15)

    return render_template('documents.html', docs=docs)


@app.route('/words')
def words():
    with h5py.File('../data.hdf', mode='r') as h5f:
        nw = h5f['n_wd'][...].sum(1)
        indices = nw.argsort()[:-21:-1]

        words = get_words_info(indices, h5f, 5)

    return render_template('words.html', words=words)


@app.route('/topic/<int:t>')
def topic(t):
    with h5py.File('../data.hdf', mode='r') as h5f:
        topic = get_topics_info([t], h5f)[0]

    return render_template('topic.html', topic=topic)


@app.route('/document/<int:d>')
def document(d):
    with h5py.File('../data.hdf', mode='r') as h5f:
        doc = get_docs_info([d], h5f)[0]

        content = h5f['documents'][str(d)][...]

        filename = h5f['filenames'][d]
        if filename != '0':
            with codecs.open('static/docsdata/%s.html' % filename, encoding='utf-8') as f:
                html = f.read()
            html = re.search(r'<body>.*</body>', html, re.DOTALL).group(0)
            html = re.sub(r'<h(\d) id="[^"]+">', r'<h\1>', html)

            ws_were = set()
            for word, w, topics, _ in content:
                if w != -1 and w not in ws_were:
                    ws_were.add(w)
                    html = re.sub(ur'(\W)(%s)(\W)' % word, r'\1<span data-word="%d" data-color="%d"><a href="#">\2</a></span>\3' % (w, topics[0]), html, flags=re.I | re.U)

            html = re.sub(r'<img class="(\w+)" src="\w+/(eqn\d+).png".*?/>',
                          r'<span class="sprite-\2"></span>',
                          html, flags=re.DOTALL | re.MULTILINE)

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

        # generate smooth topics flow
        topics_flow = content['topics'][:, 0]
        top_topics = np.bincount(topics_flow).argsort()[::-1][:5]
        topics_flow = (top_topics[:, np.newaxis] == topics_flow).T.astype(np.float32)

        wlen = 100
        window = np.ones(wlen)

        topics_flow = convolve1d(topics_flow, window / window.sum(), axis=0)
        topics_flow = list( starmap(TopicTuple, zip( top_topics, zip(*map(tuple, topics_flow)) )) )

        doc.content = list( starmap(ContentWordTuple, zip(ws, nws, words, words_norm, wtopics)) )

    return render_template('document.html', doc=doc, topics=topics, topics_flow=topics_flow, html_content=html, filename=filename)


@app.route('/word/<int:w>')
def word(w):
    with h5py.File('../data.hdf', mode='r') as h5f:
        word = get_words_info([w], h5f)[0]

    return render_template('word.html', word=word)


def get_topics_info(ts, h5f, ntop=-1):
    pds = h5f['p_td'][...][ts,:]
    nds = h5f['n_wd'][...].sum(0)
    pt = pds.dot(1.0 * nds / nds.sum())

    pws = h5f['p_wt'][...][:,ts].T
    ws = pws.argsort(axis=1)[:,::-1]
    if ntop >= 0:
        ws = ws[:,:ntop]
    words = h5f['dictionary'][...][ws]
    words = [list( starmap(WordTuple, zip(ws_r, pws_r[ws_r], words_r)) )
             for ws_r, pws_r, words_r in zip(ws, pws, words)]
    words = map(
        lambda words_r: filter(lambda w: w.np > 0, words_r),
        words)

    docs = pds.argsort(axis=1)[:, ::-1]
    if ntop >= 0:
        docs = docs[:, :ntop]
    docs = [list( starmap(DocumentTuple, zip(docs_r, pds_r[docs_r])) )
            for docs_r, pds_r in zip(docs, pds)]
    docs = map(
        lambda docs_r: filter(lambda d: d.np > 0, docs_r),
        docs)

    return list( starmap(TopicTuple, zip(ts, pt, docs, words)) )


def get_docs_info(ds, h5f, ntop=-1):
    name = h5f['docinfo'][...]['name'][ds]
    nd = h5f['n_wd'][...].sum(0)[ds]

    pts = h5f['p_td'][...][:,ds].T
    topics = pts.argsort(axis=-1)[:,::-1]
    if ntop >= 0:
        topics = topics[:,:ntop]
    topics = [list( starmap(TopicTuple, zip(topics_r, pts_r[topics_r])) )
             for topics_r, pts_r in zip(topics, pts)]
    topics = map(
        lambda topics_r: filter(lambda t: t.np > 0, topics_r),
        topics)

    nws = h5f['n_wd'][...][:,ds].T
    ws = nws.argsort()[:, ::-1]
    if ntop >= 0:
        ws = ws[:,:ntop]
    words = h5f['dictionary'][...][ws]
    words = [list( starmap(WordTuple, zip(ws_r, nws_r[ws_r], words_r)) )
             for ws_r, nws_r, words_r in zip(ws, nws, words)]
    words = map(
        lambda words_r: filter(lambda w: w.np > 0, words_r),
        words)

    return list( starmap(DocumentTuple, zip(ds, nd, name, topics, words)) )


def get_words_info(ws, h5f, ntop=-1):
    nw = h5f['n_wd'][...].sum(1)[ws]
    word = h5f['dictionary'][...][ws]

    pts = h5f['p_wt'][...][ws,:]
    topics = pts.argsort(axis=1)[:,::-1]
    if ntop >= 0:
        topics = topics[:,:ntop]
    topics = [list( starmap(TopicTuple, zipnp(topics_r, pts_r[topics_r])) )
              for topics_r, pts_r in zip(topics, pts)]
    topics = map(
        lambda topics_r: filter(lambda t: t.np > 0, topics_r),
        topics)

    nds = h5f['n_wd'][...][ws,:]
    docs = nds.argsort(axis=1)[:,::-1]
    if ntop >= 0:
        docs = docs[:,:ntop]
    docs = [list( starmap(DocumentTuple, zip(docs_r, nds_r[docs_r])) )
            for docs_r, nds_r in zip(docs, nds)]
    docs = map(
        lambda docs_r: filter(lambda d: d.np > 0, docs_r),
        docs)

    return list( starmap(WordTuple, zip(ws, nw, word, topics, docs)) )


for _, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
    if inspect.getsourcefile(f) == __file__:
        line_profile(f)

if __name__ == '__main__':
    app.run()
