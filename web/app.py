from flask import Flask
from flask.ext.assets import Environment
from flask_debugtoolbar import DebugToolbarExtension
from flask_debugtoolbar_lineprofilerpanel.profile import line_profile
import subprocess
import datetime
import inspect


app = Flask(__name__)
app.config.from_pyfile('config.cfg')
assets = Environment(app)
toolbar = DebugToolbarExtension(app)

def debug():
    assert app.debug == False, "Don't panic! You're here by request of debug()"


last_updated = None


@app.context_processor
def inject_last_updated():
    global last_updated
    if last_updated is None:
        out = subprocess.check_output("find .. -type f -print0 | xargs -0 stat --format '%Y :%y %n' | sort -nr | cut -d' ' -f2,3 | cut -d. -f1 | sed 's/://' | head -1", shell=True)
        last_updated = datetime.datetime.strptime(out, '%Y-%m-%d %H:%M:%S\n')
    return dict(last_updated=last_updated)


@app.template_filter('max')
def max_filter(iterable, attribute=None):
    if attribute is not None:
        keyfunc = lambda elem: getattr(elem, attribute)
    else:
        keyfunc = lambda elem: elem
    if not iterable:
        return None
    return keyfunc(max(iterable, key=keyfunc))



from data import *
from search import *
from views import *


for _, f in inspect.getmembers(sys.modules[__name__]):
    if not (inspect.isfunction(f) or inspect.isclass(f)):
        continue
    # if f.__module__ not in {'data', 'views', 'search'}:
    #     continue
    if inspect.isfunction(f):
        line_profile(f)
    elif inspect.isclass(f):
        for _, ff in inspect.getmembers(f, predicate=inspect.ismethod):
            line_profile(ff)


if __name__ == '__main__':
    app.run(use_reloader=app.config['DEBUG'])
