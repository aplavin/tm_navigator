#!/usr/bin/env python
import flask
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.mako import MakoTemplates
from flask_debugtoolbar import DebugToolbarExtension


app = Flask(__name__)
app.config.from_pyfile('config.cfg')
db = SQLAlchemy(app)
mako = MakoTemplates(app)
toolbar = DebugToolbarExtension(app)


def debug():
    assert not app.debug, "Don't panic! You're here by request of debug()"


def url_for_cached(endpoint, **values):
    key = (endpoint,
           tuple((k, v) for k, v in values.items() if k.startswith('_')),
           tuple(k for k in values.keys() if not k.startswith('_')))

    if key not in url_for_cached.cache:
        url_for_cached.cache[key] = flask.url_for(endpoint,
                                                  **{k: (v if k.startswith('_') else hash(k))
                                                     for k, v in values.items()})
    result = url_for_cached.cache[key]
    for k, v in values.items():
        if not k.startswith('_'):
            result = result.replace(str(hash(k)), str(v))
    return result

url_for_cached.cache = {}

@app.context_processor
def override_url_for():
    return dict(url_for=url_for_cached)

flask.helpers.url_for = url_for_cached


from views import *

if __name__ == '__main__':
    app.run(use_reloader=app.config['DEBUG'], port=5000, host='0.0.0.0')
