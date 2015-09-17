import sys
import os.path

from httpbin.core import app
import flask


@app.route('/data/<path:path>')
def send_data(path):
    basedir = os.path.realpath(os.path.dirname(__file__))
    print(basedir)
    return flask.send_from_directory(os.path.join(basedir, 'data'), path)


app.run(port=int(sys.argv[1]), debug=True, use_reloader=False)
