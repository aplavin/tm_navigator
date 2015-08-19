#!/usr/bin/env python
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.mako import MakoTemplates
from flask_debugtoolbar import DebugToolbarExtension

app = Flask(__name__)
app.config.from_pyfile('config.cfg')
db = SQLAlchemy(app)
mako = MakoTemplates(app)
toolbar = DebugToolbarExtension(app)

from slugify import slugify

app.template_filter('slug')(slugify)


def debug():
    assert not app.debug, "Don't panic! You're here by request of debug()"


from views import *

if __name__ == '__main__':
    app.run(use_reloader=app.config['DEBUG'], port=5000, host='0.0.0.0')
