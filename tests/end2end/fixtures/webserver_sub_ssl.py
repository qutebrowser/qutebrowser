# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Minimal flask webserver serving a Hello World via SSL.

This script gets called as a QProcess from end2end/conftest.py.
"""

import sys

import flask

import webserver_sub
import cheroot.ssl.builtin


app = flask.Flask(__name__)


@app.route('/')
def hello_world():
    return "Hello World via SSL!"


@app.route('/data/<path:path>')
def send_data(path):
    return webserver_sub.send_data(path)


@app.route('/redirect-http/<path:path>')
def redirect_http(path):
    """Redirect to the given (plaintext) HTTP port on localhost."""
    host, _orig_port = flask.request.server
    port = flask.request.args["port"]
    return flask.redirect(f"http://{host}:{port}/{path}")


@app.route('/favicon.ico')
def favicon():
    return webserver_sub.favicon()


@app.after_request
def log_request(response):
    return webserver_sub.log_request(response)


def main():
    webserver_sub.init_unraisable_hook()

    port = int(sys.argv[1])
    server = webserver_sub.WSGIServer(('127.0.0.1', port), app)

    ssl_dir = webserver_sub.END2END_DIR / 'data' / 'ssl'
    server.ssl_adapter = cheroot.ssl.builtin.BuiltinSSLAdapter(
        certificate=ssl_dir / 'cert.pem',
        private_key=ssl_dir / 'key.pem',
    )

    server.start()


if __name__ == '__main__':
    main()
