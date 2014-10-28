from whoosh import analysis, formats


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
