#!/usr/bin/env python3.5
import flask
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.mako import MakoTemplates
from flask_debugtoolbar import DebugToolbarExtension
from flask_morepath import Morepath
from sqlalchemy_utils import database_exists, create_database

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


@app.context_processor
def inject_models():
    import inspect
    return {k: v
            for module_name in ['models', 'routes']
            for module in [__import__(module_name)]
            for k, v in inspect.getmembers(module, inspect.isclass)}


from routes import *

# for some reason this is necessary for all routes to be available
app = mp.app

if __name__ == '__main__':
    if not database_exists(db.engine.url):
        create_database(db.engine.url)
    Base.metadata.create_all(db.engine, tables=map(lambda c: c.__table__, models_public))

    app.run(host='0.0.0.0', use_reloader=True, port=5000)
