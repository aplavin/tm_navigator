from flask import Flask, render_template, url_for, redirect, request
from flask.ext.assets import Environment
from flask_debugtoolbar import DebugToolbarExtension
from flask_debugtoolbar_lineprofilerpanel.profile import line_profile
import h5py
from collections import Counter
from recordtype import recordtype
from itertools import starmap, groupby
from math import isnan
import numpy as np
from scipy.ndimage.filters import convolve1d
import scipy.sparse
import codecs
import re
import inspect
import sys
import subprocess
import datetime
from whoosh import index, qparser, query as wh_query, analysis, sorting, highlight


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


@app.route('/')
def overview():
    with h5py.File('../data.hdf', mode='r') as h5f:
        nws = get_nwd(h5f).sum(1).A1
        ws = nws.argsort()[::-1]
        words = h5f['dictionary'][...][ws]
        words = list( starmap(WordTuple, zip(ws, nws[ws], words)) )

        nds = get_nwd(h5f).sum(0).A1
        ds = nds.argsort()[::-1]
        docs = list( starmap(DocumentTuple, zip(ds, nds[ds])) )

        ptds = h5f['p_td'][...]
        pts = ptds.dot(1.0 * nds / nds.sum())
        ts = pts.argsort()[::-1]
        topics = list( starmap(TopicTuple, zip(ts, pts[ts])) )

    return render_template('overview.html', words=words, docs=docs, topics=topics)


@app.route('/search')
@app.route('/search/', defaults={'query': ''})
@app.route('/search/<query>')
def search(query=None):
    if 'query' in request.args:
        return redirect(url_for('search', **request.args))
    return render_template('search.html', query=query or '')

class RemoveDuplicatesFilter(analysis.Filter):
    def __call__(self, stream):
        lasttext = None
        for token in stream:
            if lasttext != token.text:
                yield token
            lasttext = token.text

@app.route('/search_results/')
@app.route('/search_results/<query>')
def search_results(query=''):
    ix = index.open_dir('../whoosh_ix', readonly=True)
    qp = qparser.MultifieldParser(['title', 'authors', 'authors_ngrams', 'title_ngrams'],
                                  ix.schema,
                                  termclass=wh_query.FuzzyTerm)

    highlighter_whole = highlight.Highlighter(fragmenter=highlight.WholeFragmenter())

    def hl_whole(hit, field, text=None):
        return highlighter_whole.highlight_hit(hit, field, text)

    with ix.searcher() as searcher:
        query_parsed = qp.parse(query)

        kwargs = {}
        if 'groupby[]' in request.args:
            kwargs['groupedby'] = sorting.MultiFacet(
                items=[sorting.FieldFacet(field, allow_overlap=True) if not field.endswith('_stored') else sorting.StoredFieldFacet(field[:-7])
                       for field in request.args.getlist('groupby[]')])

        results = searcher.search(query_parsed, limit=50, **kwargs)

        if results.facet_names():
            groups = sorted(results.groups().items(), key=lambda gr: -len(gr[1]))
            grouped = [(' '.join(map(str, gr_name)) if isinstance(gr_name, tuple) else gr_name,
                        [next(hit for hit in results if hit.docnum == docnum)
                         for docnum in gr_nums])
                       for gr_name, gr_nums in groups]
        else:
            grouped = None

        return render_template('search_results.html',
                               grouped=grouped,
                               results=results,
                               hl_whole=hl_whole)


@app.route('/topics')
def topics():
    with h5py.File('../data.hdf', mode='r') as h5f:
        ptds = h5f['p_td'][...]
        nds = get_nwd(h5f).sum(0).A1
        pts = ptds.dot(1.0 * nds / nds.sum())
        indices = pts.argsort()[::-1]

        topics = get_topics_info(indices, h5f, (15, 30))

    return render_template('topics.html', topics=topics)


@app.route('/documents')
def documents():
    with h5py.File('../data.hdf', mode='r') as h5f:
        nw = get_nwd(h5f).sum(0).A1
        indices = nw.argsort()[::-1]

        docs = get_docs_info(indices, h5f, (-1, 15))

    return render_template('documents.html', docs=docs)


@app.route('/words')
def words():
    with h5py.File('../data.hdf', mode='r') as h5f:
        nw = get_nwd(h5f).sum(1).A1
        indices = nw.argsort()[::-1]

        words = get_words_info(indices, h5f, (15, 10))

    return render_template('words.html', words=words)


@app.route('/topic/<int:t>')
def topic(t):
    with h5py.File('../data.hdf', mode='r') as h5f:
        topic = get_topics_info([t], h5f)[0]

    return render_template('topic.html', topic=topic)


@app.route('/document/<slug>')
@app.route('/document/<int:d>')
@app.route('/document/<int:d>/<slug>')
def document(slug=None, d=None):
    with h5py.File('../data.hdf', mode='r') as h5f:
        if d is None:
            slugs = h5f['metadata']['slug']
            d = np.nonzero(slugs == slug)[0][0]

        doc = get_docs_info([d], h5f)[0]

        content = h5f['documents'][str(d)][...]

        filename = h5f['metadata']['filename', d]
        with codecs.open('static/docsdata/%s.html' % filename, encoding='utf-8') as f:
            html = f.read()
        # html = re.search(r'<body>.*</body>', html, re.DOTALL).group(0)
        # html = re.sub(r'<h(\d) id="[^"]+">', r'<h\1>', html)

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

        html = html_new

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
        wlen = 100
        window = np.bartlett(wlen)
        topics_flow = convolve1d(topics_flow, window / window.sum(), axis=0)
        topics_flow = list( starmap(TopicTuple, zip( [t.t for t in doc.topics], zip(*map(tuple, topics_flow)) )) )

    return render_template('document.html',
                            doc=doc,
                            topics_flow=topics_flow,
                            html_content=html,
                            topics_in_content=topics_in_content,
                            filename=filename)


@app.route('/word/<int:w>')
def word(w):
    with h5py.File('../data.hdf', mode='r') as h5f:
        word = get_words_info([w], h5f)[0]

    return render_template('word.html', word=word)


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


for _, f in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
    if inspect.getsourcefile(f) == __file__:
        line_profile(f)

if __name__ == '__main__':
    app.run()
