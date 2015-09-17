import re
import sys
import socket
import functools
import os.path

import pytest
import pytestqt.plugin
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QProcess, QObject


class InvalidLine(Exception):

    """Exception raised when HTTPBin prints a line which is not parsable."""

    pass


class HTTPBin(QObject):

    ready = pyqtSignal()
    got_new_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._invalid = False
        self._visited_urls = []
        self.port = self._get_port()
        self.proc = QProcess()
        self.proc.setReadChannel(QProcess.StandardError)

    def _get_port(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def get_visited(self):
        self.proc.waitForReadyRead(500)
        self.read_urls()
        return self._visited_urls

    @pyqtSlot()
    def read_urls(self):
        while self.proc.canReadLine():
            line = self.proc.readLine()
            line = bytes(line).decode('utf-8').rstrip('\n')
            print(line)

            if line == (' * Running on http://127.0.0.1:{}/ (Press CTRL+C to '
                        'quit)'.format(self.port)):
                self.ready.emit()
                continue

            match = re.match(r'.*"(GET [^ ]*) .*', line)  # FIXME
            if match is None:
                self._invalid = True
                print("INVALID: {}".format(line))
                continue
            url = match.group(1)
            print(url)
            self._visited_urls.append(url)
            self.got_new_url.emit(url)

    def start(self):
        filename = os.path.join(os.path.dirname(__file__), 'webserver.py')
        self.proc.start(sys.executable, [filename, str(self.port)])
        ok = self.proc.waitForStarted()
        assert ok
        self.proc.readyRead.connect(self.read_urls)

    def after_test(self):
        self._visited_urls.clear()
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
