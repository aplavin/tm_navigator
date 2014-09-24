
from whoosh import analysis, formats, index, qparser, query as wh_query, highlight, sorting


@app.route('/search')
@app.route('/search/', defaults={'query': ''})
@app.route('/search/<query>')
def search(query=None):
    return render_template('document/search.html', query=query or '')

class RemoveDuplicatesFilter(analysis.Filter):
    def __call__(self, stream):
        lasttext = None
        for token in stream:
            if lasttext != token.text:
                yield token
            lasttext = token.text

class WithData(formats.Format):

    def word_values(self, value, analyzer, **kwargs):
        fb = self.field_boost

        for text, val in value:
            yield (text, 1, fb, formats.pack_float(val))

    def decode_data(self, valuestring):
        return formats.unpack_float(valuestring)[0]

    def decode_frequency(self, valuestring):
        return 1

    def decode_weight(self, v):
        return self.field_boost

@app.route('/search_results/')
@app.route('/search_results/<query>')
def search_results(query='*'):
    ix = index.open_dir('../whoosh_ix', readonly=True, indexname='docs')

    fields = ['title', 'authors', 'authors_ngrams', 'title_ngrams']
    if request.args.get('in_text', False) == 'true':
        fields = ['content'] + fields
    qp = qparser.MultifieldParser(fields,
                                  ix.schema,
                                  termclass=wh_query.FuzzyTerm)

    highlighter_whole = highlight.Highlighter(fragmenter=highlight.WholeFragmenter())
    def hl_whole(hit, field, text=None):
        return highlighter_whole.highlight_hit(hit, field, text)

    highlighter_content = highlight.Highlighter(
        fragmenter=highlight.PinpointFragmenter(surround=50, maxchars=1000, autotrim=True),
        formatter=highlight.HtmlFormatter(between='<hr/>')
    )
    def hl_content(hit):
        return highlighter_content.highlight_hit(hit, 'content')

    def htopics(hit):
        topics = [TopicTuple(name, ptd)
                  for name, ptd in searcher.vector_as('data', hit.docnum, 'topics')]
        topics.sort(key=lambda t: t.np, reverse=True)
        return topics

    with ix.searcher() as searcher:
        query_parsed = qp.parse(query)

        kwargs = {}
        if 'groupby[]' in request.args:
            kwargs['groupedby'] = sorting.MultiFacet(
                items=[sorting.FieldFacet(field, allow_overlap=True) if not field.endswith('_stored') else sorting.StoredFieldFacet(field[:-7])
                       for field in request.args.getlist('groupby[]')])

        results = searcher.search(query_parsed, limit=50, terms=True, **kwargs)

        if not results:
            corrected = searcher.correct_query(query_parsed, query)
            if corrected.string != query:
                corrected.html = corrected.format_string(highlight.HtmlFormatter())
            else:
                corrected = None
        else:
            corrected = None

        if results.facet_names():
            groups = sorted(results.groups().items(), key=lambda gr: (-len(gr[1]), gr[0]))
            grouped = [(' '.join(map(str, gr_name)) if isinstance(gr_name, tuple) else gr_name,
                        [next(hit for hit in results if hit.docnum == docnum)
                         for docnum in gr_nums])
                       for gr_name, gr_nums in groups]
            results_cnt = sum(len(gr) for _, gr in grouped)
        else:
            grouped = None
            results_cnt = len(results)

        return render_template('document/search_results.html',
                               query=query,
                               grouped=grouped,
                               results=results,
                               results_cnt=results_cnt,
                               hl_whole=hl_whole,
                               hl_content=hl_content,
                               htopics=htopics,
                               corrected=corrected)