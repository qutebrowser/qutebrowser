# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Minimal flask webserver serving a Hello World via SSL.

This script gets called as a QProcess from end2end/conftest.py.
"""

import ssl
import sys
import logging
import pathlib

import flask

import webserver_sub


app = flask.Flask(__name__)


@app.route('/')
def hello_world():
    return "Hello World via SSL!"


@app.route('/data/<path:path>')
def send_data(path):
    return webserver_sub.send_data(path)


@app.route('/favicon.ico')
def favicon():
    return webserver_sub.favicon()


@app.after_request
def log_request(response):
    return webserver_sub.log_request(response)


@app.before_first_request
def turn_off_logging():
    # Turn off werkzeug logging after the startup message has been printed.
    logging.getLogger('werkzeug').setLevel(logging.ERROR)


def main():
    end2end_dir = pathlib.Path(__file__).resolve().parents[1]
    ssl_dir = end2end_dir / 'data' / 'ssl'
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain((ssl_dir / 'cert.pem'),
                            (ssl_dir / 'key.pem'))
    app.run(port=int(sys.argv[1]), debug=False, ssl_context=context)


if __name__ == '__main__':
    main()
