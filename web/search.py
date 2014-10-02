from lazylist import LazyList
from whoosh import (analysis, formats, index, qparser, sorting, scoring,
                    query as wh_query, highlight as wh_highlight)


class RemoveDuplicatesFilter(analysis.Filter):
    def __call__(self, stream):
        lasttext = None
        for token in stream:
            if lasttext != token.text:
                yield token
            lasttext = token.text


class WithFloatData(formats.Format):

    def word_values(self, value, analyzer, **kwargs):
        fb = self.field_boost

        for text, val in value:
            yield (text, 1, fb * val, formats.pack_float(val))

    def decode_data(self, valuestring):
        return formats.unpack_float(valuestring)[0]

    def decode_frequency(self, valuestring):
        return 1

    def decode_weight(self, v):
        return self.field_boost


highlighters = {
    'whole': wh_highlight.Highlighter(fragmenter=wh_highlight.WholeFragmenter()),
    'pinpoint': wh_highlight.Highlighter(
        fragmenter=wh_highlight.PinpointFragmenter(surround=100, maxchars=1000, autotrim=True),
        formatter=wh_highlight.HtmlFormatter(between='<hr/>')
    )
}


def highlight(hit, hl_name, fields, fallback=None, text=None):
    for field in fields:
        if text:
            hl = highlighters[hl_name].highlight_hit(hit, field, text)
        else:
            hl = highlighters[hl_name].highlight_hit(hit, field)
        if hl:
            return hl
    if fallback is not None:
        return hit[fallback]


def vector_data(indexname, hit, field):
    viter = get_searcher(indexname).vector_as('data', hit.docnum, field)
    return LazyList(viter)


def vector_length(indexname, hit, field):
    return get_searcher(indexname).doc_field_length(hit.docnum, field)


searchers = {}


def get_searcher(indexname):
    if indexname not in searchers:
        ix = index.open_dir('../whoosh_ix', readonly=True, indexname=indexname)
        searchers[indexname] = ix.searcher()
    return searchers[indexname]


def do_search(indexname, query, fields, groupby, kwargs=None):
    searcher = get_searcher(indexname)

    qp = qparser.MultifieldParser(fields,
                                  searcher.schema,
                                  termclass=wh_query.FuzzyTerm)

    if query != '':
        query_parsed = qp.parse(query)
    else:
        query_parsed = wh_query.Every()

    kwargs_ = {'limit': 50, 'terms': True}
    if groupby:
        kwargs_['groupedby'] = sorting.MultiFacet(items=groupby)
    kwargs_.update(kwargs or {})

    results = searcher.search(query_parsed, **kwargs_)

    if not results:
        corrected = searcher.correct_query(query_parsed, query)
        if corrected.string != query:
            corrected.html = corrected.format_string(wh_highlight.HtmlFormatter())
        else:
            corrected = None
    else:
        corrected = None

    if results.facet_names():
        groups = sorted(results.groups().dict.items(), key=lambda gr: (-len(gr[1]), gr[0]))

        indices = {}
        for i, hit in enumerate(results):
            indices[hit.docnum] = i

        grouped = [(' '.join(map(str, gr_name)) if isinstance(gr_name, tuple) else gr_name,
                    [results[indices[docnum]]
                     for sortkey, value, docnum in gr_nums])
                   for gr_name, gr_nums in groups]
        results_cnt = sum(len(gr) for _, gr in grouped)
    else:
        groups = None
        grouped = None
        results_cnt = len(results)

    return dict(
        groups=groups,
        grouped=grouped,
        results=results,
        results_cnt=results_cnt,
        corrected=corrected)


def get_similar(indexname, docnum, fieldname):
    searcher = get_searcher(indexname)

    def weightlen_score_fn(searcher, fieldname, text, matcher):
        w = matcher.weight()
        l = searcher.doc_field_length(matcher.id(), fieldname, 0)
        return (w - (1.0 * l / searcher.max_field_length(fieldname))) / score_max

    wl_weighting = scoring.FunctionWeighting(weightlen_score_fn)

    old_weighting = searcher.weighting
    searcher.weighting = wl_weighting

    vec = searcher.vector(docnum, fieldname)
    cur_values = list(vec.all_ids())

    score_max = len(cur_values) * (1 - 1.0 * len(cur_values) / searcher.max_field_length(fieldname))

    query = wh_query.Or([wh_query.Term(fieldname, term) for term in cur_values])
    results = searcher.search(query, limit=None, mask={docnum})
    results.highlighter.fragmenter = wh_highlight.WholeFragmenter()

    searcher.weighting = old_weighting

    return results


def get_completions(indexname, fields, prefix, as_flat=False):
    searcher = get_searcher(indexname)

    seen_terms = set()
    for field in fields:
        expansions =((term, searcher.frequency(field, term))
                     for term in searcher.reader().expand_prefix(field, prefix)
                     if '.' not in term and term not in seen_terms)
        expansions = sorted(expansions, key=lambda (t, f): f, reverse=True)
        seen_terms.update(t for t, f in expansions)

        if as_flat:
            for t, f in expansions:
                yield field, t, f
        else:
            yield (field, expansions)
