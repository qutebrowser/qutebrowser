# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Web server for end2end tests.

This script gets called as a QProcess from end2end/conftest.py.

Some of the handlers here are inspired by the server project, but simplified
for qutebrowser's needs. Note that it probably doesn't handle e.g. multiple
parameters or headers with the same name properly.
"""

import sys
import json
import time
import signal
import os
import threading
from http import HTTPStatus

import cheroot.wsgi
import flask

app = flask.Flask(__name__)
_redirect_later_event = None


@app.route('/')
def root():
    """Show simple text."""
    return flask.Response(b'qutebrowser test webserver, '
                          b'<a href="/user-agent">user agent</a>')


@app.route('/data/<path:path>')
@app.route('/data2/<path:path>')  # for per-URL settings
def send_data(path):
    """Send a given data file to qutebrowser.

    If a directory is requested, its index.html is sent.
    """
    if hasattr(sys, 'frozen'):
        basedir = os.path.realpath(os.path.dirname(sys.executable))
        data_dir = os.path.join(basedir, 'end2end', 'data')
    else:
        basedir = os.path.join(os.path.realpath(os.path.dirname(__file__)),
                               '..')
        data_dir = os.path.join(basedir, 'data')
    print(basedir)
    if os.path.isdir(os.path.join(data_dir, path)):
        path += '/index.html'
    return flask.send_from_directory(data_dir, path)


@app.route('/redirect-later')
def redirect_later():
    """302 redirect to / after the given delay.

    If delay is -1, wait until a request on redirect-later-continue is done.
    """
    global _redirect_later_event
    delay = float(flask.request.args.get('delay', '1'))
    if delay == -1:
        _redirect_later_event = threading.Event()
        ok = _redirect_later_event.wait(timeout=30 * 1000)
        assert ok
        _redirect_later_event = None
    else:
        time.sleep(delay)
    x = flask.redirect('/')
    return x


@app.route('/redirect-later-continue')
def redirect_later_continue():
    """Continue a redirect-later request."""
    if _redirect_later_event is None:
        return flask.Response(b'Timed out or no redirect pending.')
    else:
        _redirect_later_event.set()
        return flask.Response(b'Continued redirect.')


@app.route('/redirect-self')
def redirect_self():
    """302 Redirects to itself."""
    return app.make_response(flask.redirect(flask.url_for('redirect_self')))


@app.route('/redirect/<int:n>')
def redirect_n_times(n):
    """302 Redirects n times."""
    assert n > 0
    return flask.redirect(flask.url_for('redirect_n_times', n=n-1))


@app.route('/relative-redirect')
def relative_redirect():
    """302 Redirect once."""
    response = app.make_response('')
    response.status_code = HTTPStatus.FOUND
    response.headers['Location'] = flask.url_for('root')
    return response


@app.route('/absolute-redirect')
def absolute_redirect():
    """302 Redirect once."""
    response = app.make_response('')
    response.status_code = HTTPStatus.FOUND
    response.headers['Location'] = flask.url_for('root', _external=True)
    return response


@app.route('/redirect-to')
def redirect_to():
    """302/3XX Redirects to the given URL."""
    # We need to build the response manually and convert to UTF-8 to prevent
    # werkzeug from "fixing" the URL. This endpoint should set the Location
    # header to the exact string supplied.
    response = app.make_response('')
    response.status_code = HTTPStatus.FOUND
    response.headers['Location'] = flask.request.args['url'].encode('utf-8')
    return response


@app.route('/content-size')
def content_size():
    """Send two bytes of data without a content-size."""
    def generate_bytes():
        yield b'*'
        time.sleep(0.2)
        yield b'*'

    response = flask.Response(generate_bytes(), headers={
        "Content-Type": "application/octet-stream",
    })
    response.status_code = HTTPStatus.OK
    return response


@app.route('/twenty-mb')
def twenty_mb():
    """Send 20MB of data."""
    def generate_bytes():
        yield b'*' * 20 * 1024 * 1024

    response = flask.Response(generate_bytes(), headers={
        "Content-Type": "application/octet-stream",
        "Content-Length": str(20 * 1024 * 1024),
    })
    response.status_code = HTTPStatus.OK
    return response


@app.route('/500-inline')
def internal_error_attachment():
    """A 500 error with Content-Disposition: inline."""
    response = flask.Response(b"", headers={
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'inline; filename="attachment.jpg"',
    })
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    return response


@app.route('/500')
def internal_error():
    """A normal 500 error."""
    r = flask.make_response()
    r.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    return r


@app.route('/cookies')
def view_cookies():
    """Show cookies."""
    return flask.jsonify(cookies=flask.request.cookies)


@app.route('/cookies/set')
def set_cookies():
    """Set cookie(s) as provided by the query string."""
    r = app.make_response(flask.redirect(flask.url_for('view_cookies')))
    for key, value in flask.request.args.items():
        r.set_cookie(key=key, value=value)
    return r


@app.route('/basic-auth/<user>/<passwd>')
def basic_auth(user='user', passwd='passwd'):
    """Prompt the user for authorization using HTTP Basic Auth."""
    auth = flask.request.authorization
    if not auth or auth.username != user or auth.password != passwd:
        r = flask.make_response()
        r.status_code = HTTPStatus.UNAUTHORIZED
        r.headers = {'WWW-Authenticate': 'Basic realm="Fake Realm"'}
        return r

    return flask.jsonify(authenticated=True, user=user)


@app.route('/drip')
def drip():
    """Drip data over a duration."""
    duration = float(flask.request.args.get('duration'))
    numbytes = int(flask.request.args.get('numbytes'))
    pause = duration / numbytes

    def generate_bytes():
        for _ in range(numbytes):
            yield "*".encode('utf-8')
            time.sleep(pause)

    response = flask.Response(generate_bytes(), headers={
        "Content-Type": "application/octet-stream",
        "Content-Length": str(numbytes),
    })
    response.status_code = HTTPStatus.OK
    return response


@app.route('/404')
def status_404():
    r = flask.make_response()
    r.status_code = HTTPStatus.NOT_FOUND
    return r


@app.route('/headers')
def view_headers():
    """Return HTTP headers."""
    return flask.jsonify(headers=dict(flask.request.headers))


@app.route('/response-headers')
def response_headers():
    """Return a set of response headers from the query string."""
    headers = flask.request.args
    response = flask.jsonify(headers)
    response.headers.extend(headers)

    response = flask.jsonify(dict(response.headers))
    response.headers.extend(headers)
    return response


@app.route('/query')
def query():
    return flask.jsonify(flask.request.args)


@app.route('/user-agent')
def view_user_agent():
    """Return User-Agent."""
    return flask.jsonify({'user-agent': flask.request.headers['user-agent']})


@app.route('/favicon.ico')
def favicon():
    basedir = os.path.join(os.path.realpath(os.path.dirname(__file__)),
                           '..', '..', '..')
    return flask.send_from_directory(os.path.join(basedir, 'icons'),
                                     'qutebrowser.ico',
                                     mimetype='image/vnd.microsoft.icon')


@app.after_request
def log_request(response):
    """Log a webserver request."""
    request = flask.request
    data = {
        'verb': request.method,
        'path': request.full_path if request.query_string else request.path,
        'status': response.status_code,
    }
    print(json.dumps(data), file=sys.stderr, flush=True)
    return response


class WSGIServer(cheroot.wsgi.Server):

    """A custom WSGIServer that prints a line on stderr when it's ready.

    Attributes:
        _ready: Internal state for the 'ready' property.
        _printed_ready: Whether the initial ready message was printed.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ready = False
        self._printed_ready = False

    @property
    def ready(self):
        return self._ready

    @ready.setter
    def ready(self, value):
        if value and not self._printed_ready:
            print(' * Running on http://127.0.0.1:{}/ (Press CTRL+C to quit)'
                  .format(self.bind_addr[1]), file=sys.stderr, flush=True)
            self._printed_ready = True
        self._ready = value


def main():
    if hasattr(sys, 'frozen'):
        basedir = os.path.realpath(os.path.dirname(sys.executable))
        app.template_folder = os.path.join(basedir, 'end2end', 'templates')
    port = int(sys.argv[1])
    server = WSGIServer(('127.0.0.1', port), app)

    signal.signal(signal.SIGTERM, lambda *args: server.stop())

    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    main()
