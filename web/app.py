from flask import Flask
from flask.ext.assets import Environment
from flask_debugtoolbar import DebugToolbarExtension
import subprocess
import datetime


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


from views import *


# for error in range(400, 420) + range(500, 506):
#     app.errorhandler(error)(views.error_handler)
# app.errorhandler(Exception)(views.error_handler)


if __name__ == '__main__':
    app.run(use_reloader=app.config['DEBUG'])
