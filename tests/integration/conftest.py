import re
import sys
import socket
import functools
import os.path
import collections

import pytest
import pytestqt.plugin
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QProcess, QObject


Request = collections.namedtuple('Request', 'verb, url')


class InvalidLine(Exception):

    """Exception raised when HTTPBin prints a line which is not parsable."""

    pass


class HTTPBin(QObject):

    ready = pyqtSignal()
    new_request = pyqtSignal(Request)

    LOG_RE = re.compile(r"""
        (?P<host>[^ ]*)
        \ ([^ ]*) # ignored
        \ (?P<user>[^ ]*)
        \ \[(?P<date>[^]]*)\]
        \ "(?P<request>
            (?P<verb>[^ ]*)
            \ (?P<url>[^ ]*)
            \ (?P<protocol>[^ ]*)
        )"
        \ (?P<status>[^ ]*)
        \ (?P<size>[^ ]*)
    """, re.VERBOSE)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._invalid = False
        self._requests = []
        self.port = self._get_port()
        self.proc = QProcess()
        self.proc.setReadChannel(QProcess.StandardError)

    def _get_port(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def get_requests(self):
        self.proc.waitForReadyRead(500)
        self.read_log()
        return self._requests

    @pyqtSlot()
    def read_log(self):
        while self.proc.canReadLine():
            line = self.proc.readLine()
            line = bytes(line).decode('utf-8').rstrip('\n')
            print(line)

            if line == (' * Running on http://127.0.0.1:{}/ (Press CTRL+C to '
                        'quit)'.format(self.port)):
                self.ready.emit()
                continue

            match = self.LOG_RE.match(line)
            if match is None:
                self._invalid = True
                print("INVALID: {}".format(line))
                continue

            # FIXME do we need to allow other options?
            assert match.group('protocol') == 'HTTP/1.1'

            request = Request(verb=match.group('verb'), url=match.group('url'))
            print(request)
            self._requests.append(request)
            self.new_request.emit(request)

    def start(self):
        filename = os.path.join(os.path.dirname(__file__), 'webserver.py')
        self.proc.start(sys.executable, [filename, str(self.port)])
        ok = self.proc.waitForStarted()
        assert ok
        self.proc.readyRead.connect(self.read_log)

    def after_test(self):
        self._requests.clear()
        if self._invalid:
            raise InvalidLine

    def cleanup(self):
        self.proc.terminate()
        self.proc.waitForFinished()


@pytest.yield_fixture(scope='session', autouse=True)
def httpbin(qapp):
    httpbin = HTTPBin()

    blocker = pytestqt.plugin.SignalBlocker(timeout=5000, raising=True)
    blocker.connect(httpbin.ready)
    with blocker:
        httpbin.start()

    yield httpbin

    httpbin.cleanup()


@pytest.yield_fixture(autouse=True)
def httpbin_clean(httpbin):
    yield
    httpbin.after_test()
