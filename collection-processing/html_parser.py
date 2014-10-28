from HTMLParser import HTMLParser
import pymorphy2
import re
from collections import defaultdict


class MyHTMLParser(HTMLParser):

    def __init__(self, html):
        HTMLParser.__init__(self)

        self.html = html

        self.morph = pymorphy2.MorphAnalyzer()
        # https://pymorphy2.readthedocs.org/en/latest/user/grammemes.html
        self.ignore_tags = ['LATN', 'PNCT', 'NUMB', 'ROMN', 'UNKN',
                            'PREP', 'CONJ', 'PRCL', 'INTJ', 'NPRO', 'NUMR', 'Abbr']
        self.minwlen = 4

        self.lineslens = map(lambda l: len(l) + 1, self.html.split('\n'))

        self.inheader = None
        self.metadata = defaultdict(str)

        self.words = []
        self.cntlatin = 0
        self.started = False

        self.feed(self.html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'body':
            self.started = True
        elif re.match(r'h\d', tag) and 'class' in attrs:
            self.inheader = attrs['class']

    def handle_endtag(self, tag):
        if len(tag) == 2 and tag[0] == 'h':
            if self.inheader:
                self.metadata[self.inheader] = self.metadata[self.inheader].strip()
            self.inheader = None

    def handle_data(self, data):
        if self.inheader:
            self.metadata[self.inheader] += data

        lineno, loffset = self.getpos()
        data_offset = sum(self.lineslens[:lineno-1]) + loffset
        sdata = self.html[data_offset: data_offset+len(data)]
        assert data == sdata, (data, sdata)

        matches = re.finditer(r'\b\w+\b', data, flags=re.U)
        for m in matches:
            word = m.group(0)
            if len(word) < self.minwlen:
                continue

            start = data_offset + m.start()
            end = data_offset + m.end()
            assert word == self.html[start:end]

            wparsed = self.morph.parse(word)[0]
            wnorm = wparsed.normal_form
            if 'LATN' in wparsed.tag:
                self.cntlatin += 1
            if not any(ign in wparsed.tag for ign in self.ignore_tags):
                self.words.append((word, wnorm, start, end))
