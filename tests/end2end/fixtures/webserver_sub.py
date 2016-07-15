# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""httpbin web server for end2end tests.

This script gets called as a QProcess from end2end/conftest.py.
"""

import sys
import json
import time
import signal
import os
import threading

from httpbin.core import app
from httpbin.structures import CaseInsensitiveDict
import cherrypy.wsgiserver
import flask


_redirect_later_event = None


@app.route('/data/<path:path>')
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
        path = path + '/index.html'
    return flask.send_from_directory(data_dir, path)


@app.route('/custom/redirect-later')
def redirect_later():
    """302 redirect to / after the given delay.

    If delay is -1, wait until a request on redirect-later-continue is done.
    """
    global _redirect_later_event
    args = CaseInsensitiveDict(flask.request.args.items())
    delay = int(args.get('delay', '1'))
    if delay == -1:
        _redirect_later_event = threading.Event()
        ok = _redirect_later_event.wait(timeout=30 * 1000)
        assert ok
        _redirect_later_event = None
    else:
        time.sleep(delay)
    x = flask.redirect('/')
    return x


@app.route('/custom/redirect-later-continue')
def redirect_later_continue():
    """Continue a redirect-later request."""
    _redirect_later_event.set()
    return flask.Response(b'Continued redirect.')


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


class WSGIServer(cherrypy.wsgiserver.CherryPyWSGIServer):

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
