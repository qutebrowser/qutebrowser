import ssl
import sys
import json
import logging
import os.path

import flask


app = flask.Flask(__name__)


@app.route('/')
def hello_world():
    return "Hello World via SSL!"


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


@app.before_first_request
def turn_off_logging():
    # Turn off werkzeug logging after the startup message has been printed.
    logging.getLogger('werkzeug').setLevel(logging.ERROR)


def main():
    ssl_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                           'data', 'ssl')
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain(os.path.join(ssl_dir, 'cert.pem'),
                            os.path.join(ssl_dir, 'key.pem'))
    app.run(port=int(sys.argv[1]), debug=False, ssl_context=context)


if __name__ == '__main__':
    main()
