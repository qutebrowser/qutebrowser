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
import threading
from datetime import datetime

from httpbin.core import app
from httpbin.structures import CaseInsensitiveDict
import cherrypy.wsgiserver
import flask

server = None

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


def ready_checker(server):
    """Wait until the server is ready and display the ready message."""
    while not server.ready:
        time.sleep(0.2)
    print(' * Running on http://127.0.0.1:{}/ (Press CTRL+C to quit)'
          .format(server.bind_addr[1]), file=sys.stderr, flush=True)


def shutdown(*args):
    """Stop the server."""
    if server is None:
        return
    server.stop()


def main():
    global server
    if hasattr(sys, 'frozen'):
        basedir = os.path.realpath(os.path.dirname(sys.executable))
        app.template_folder = os.path.join(basedir, 'integration', 'templates')
    port = int(sys.argv[1])
    server = cherrypy.wsgiserver.CherryPyWSGIServer(
        ('0.0.0.0', port), app)  # pylint: disable=no-member

    checker = threading.Thread(target=ready_checker, args=[server])
    checker.start()
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server.start()
    except KeyboardInterrupt:
        shutdown()


if __name__ == '__main__':
    main()
