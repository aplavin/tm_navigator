#!/usr/bin/env python
import flask
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.mako import MakoTemplates
from flask_debugtoolbar import DebugToolbarExtension
from flask_morepath import Morepath


app = Flask(__name__)
mp = Morepath(app)
app.config.from_pyfile('config.cfg')
db = SQLAlchemy(app)
mako = MakoTemplates(app)
toolbar = DebugToolbarExtension(app)


@app.context_processor
def override_url_for():
    return dict(url_for=mp.url_for)

flask.helpers.url_for = mp.url_for


import inspect


@app.context_processor
def inject_models():
    return {k: v
            for module_name in ['models', 'assessment_models', 'routes']
            for module in [__import__(module_name)]
            for k, v in inspect.getmembers(module, inspect.isclass)}


from routes import *
app = mp.app

if __name__ == '__main__':
    app.run(use_reloader=True, port=5000)
