from flask import Flask, render_template
import h5py


app = Flask(__name__)


@app.route('/')
def overview():
    return render_template('overview.html')


if __name__ == '__main__':
    app.run()
