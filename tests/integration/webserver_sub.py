# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""httpbin web server for integration tests.

This script gets called as a QProcess from integration/conftest.py.
"""

import sys
import time
import signal
import os
from datetime import datetime

from httpbin.core import app
from httpbin.structures import CaseInsensitiveDict
import cherrypy.wsgiserver
import flask


@app.route('/data/<path:path>')
def send_data(path):
    if hasattr(sys, 'frozen'):
        basedir = os.path.realpath(os.path.dirname(sys.executable))
        data_dir = os.path.join(basedir, 'integration', 'data')
    else:
        basedir = os.path.realpath(os.path.dirname(__file__))
        data_dir = os.path.join(basedir, 'data')
    print(basedir)
    return flask.send_from_directory(data_dir, path)


@app.route('/custom/redirect-later')
def redirect_later():
    """302 redirects to / after the given delay."""
    args = CaseInsensitiveDict(flask.request.args.items())
    time.sleep(int(args.get('delay', '1')))
    return flask.redirect('/')


@app.after_request
def log_request(response):
    request = flask.request
    template = '127.0.0.1 - - [{date}] "{verb} {path} {http}" {status} -'
    print(template.format(
        date=datetime.now().strftime('%d/%b/%Y %H:%M:%S'),
        verb=request.method,
        path=request.full_path if request.query_string else request.path,
        http=request.environ['SERVER_PROTOCOL'],
        status=response.status_code,
    ), file=sys.stderr, flush=True)
    return response


class WSGIServer(cherrypy.wsgiserver.CherryPyWSGIServer):

    """A custom WSGIServer that prints a line on stderr when it's ready."""

    # pylint: disable=no-member

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
    # pylint: disable=no-member
    # "Instance of 'WSGIServer' has no 'start' member (no-member)"
    # "Instance of 'WSGIServer' has no 'stop' member (no-member)"

    if hasattr(sys, 'frozen'):
        basedir = os.path.realpath(os.path.dirname(sys.executable))
        app.template_folder = os.path.join(basedir, 'integration', 'templates')
    port = int(sys.argv[1])
    server = WSGIServer(('127.0.0.1', port), app)

    signal.signal(signal.SIGTERM, lambda *args: server.stop())

    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    main()
