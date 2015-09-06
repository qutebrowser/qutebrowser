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

"""Tests for qutebrowser.misc.ipc."""

import getpass
import collections
import logging
import json
from unittest import mock

import pytest
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtNetwork import QLocalServer, QLocalSocket, QAbstractSocket
from PyQt5.QtTest import QSignalSpy

import qutebrowser
from qutebrowser.misc import ipc
from qutebrowser.utils import objreg
from helpers import stubs  # pylint: disable=import-error


Args = collections.namedtuple('Args', 'basedir')


@pytest.yield_fixture
def ipc_server(qapp, qtbot):
    server = ipc.IPCServer('qutebrowser-test')
    yield server
    if (server._socket is not None and
            server._socket.state() != QLocalSocket.UnconnectedState):
        with qtbot.waitSignal(server._socket.disconnected, raising=False):
            server._socket.abort()
    try:
        server.shutdown()
    except ipc.Error:
        pass


@pytest.yield_fixture
def qlocalserver(qapp):
    server = QLocalServer()
    yield server
    server.close()
    server.deleteLater()


@pytest.yield_fixture
def qlocalsocket(qapp):
    socket = QLocalSocket()
    yield socket
    socket.disconnectFromServer()
    if socket.state() != QLocalSocket.UnconnectedState:
        socket.waitForDisconnected(1000)


class FakeSocket(QObject):

    """A stub for a QLocalSocket.

    Args:
        _can_read_line_val: The value returned for canReadLine().
        _error_val: The value returned for error().
        _state_val: The value returned for state().
        _connect_successful: The value returned for waitForConnected().
        deleted: Set to True if deleteLater() was called.
    """

    readyRead = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, *, error=QLocalSocket.UnknownSocketError, state=None,
                 data=None, connect_successful=True, parent=None):
        super().__init__(parent)
        self._error_val = error
        self._state_val = state
        self._data = data
        self._connect_successful = connect_successful
        self.error = stubs.FakeSignal('error', func=self._error)
        self.deleted = False

    def _error(self):
        return self._error_val

    def state(self):
        return self._state_val

    def canReadLine(self):
        return bool(self._data)

    def readLine(self):
        firstline, mid, rest = self._data.partition(b'\n')
        self._data = rest
        return firstline + mid

    def deleteLater(self):
        self.deleted = True

    def errorString(self):
        return "Error string"

    def abort(self):
        self.disconnected.emit()

    def disconnectFromServer(self):
        pass

    def connectToServer(self, _name):
        pass

    def waitForConnected(self, _time):
        return self._connect_successful

    def writeData(self, _data):
        pass

    def waitForBytesWritten(self, _time):
        pass

    def waitForDisconnected(self, _time):
        pass


class FakeServer:

    def __init__(self, socket):
        self._socket = socket

    def nextPendingConnection(self):
        socket = self._socket
        self._socket = None
        return socket

    def close(self):
        pass

    def deleteLater(self):
        pass


def test_getpass_getuser():
    """Make sure getpass.getuser() returns something sensible."""
    assert getpass.getuser()


@pytest.mark.parametrize('username, basedir, expected', [
    ('florian', None, 'qutebrowser-florian'),
    ('florian', '/x', 'qutebrowser-florian-cc8755609ad61864910f145119713de9'),
])
def test_get_socketname(username, basedir, expected):
    assert ipc._get_socketname(basedir, user=username) == expected


def test_get_socketname_no_user():
    assert ipc._get_socketname(None).startswith('qutebrowser-')


class TestExceptions:

    def test_listen_error(self, qlocalserver):
        qlocalserver.listen(None)
        exc = ipc.ListenError(qlocalserver)
        assert exc.code == 2
        assert exc.message == "QLocalServer::listen: Name error"
        msg = ("Error while listening to IPC server: QLocalServer::listen: "
               "Name error (error 2)")
        assert str(exc) == msg

        with pytest.raises(ipc.Error):
            raise exc

    def test_socket_error(self, qlocalserver):
        socket = FakeSocket(error=QLocalSocket.ConnectionRefusedError)
        exc = ipc.SocketError("testing", socket)
        assert exc.code == QLocalSocket.ConnectionRefusedError
        assert exc.message == "Error string"
        assert str(exc) == "Error while testing: Error string (error 0)"

        with pytest.raises(ipc.Error):
            raise exc


class TestListen:

    @pytest.mark.posix
    def test_remove_error(self, ipc_server, monkeypatch):
        """Simulate an error in _remove_server."""
        monkeypatch.setattr(ipc_server, '_socketname', None)
        with pytest.raises(ipc.Error) as excinfo:
            ipc_server.listen()
        assert str(excinfo.value) == "Error while removing server None!"

    def test_error(self, ipc_server, monkeypatch):
        """Simulate an error while listening."""
        monkeypatch.setattr('qutebrowser.misc.ipc.QLocalServer.removeServer',
                            lambda self: True)
        monkeypatch.setattr(ipc_server, '_socketname', None)
        with pytest.raises(ipc.ListenError):
            ipc_server.listen()

    @pytest.mark.posix
    def test_in_use(self, qlocalserver, ipc_server, monkeypatch):
        monkeypatch.setattr('qutebrowser.misc.ipc.QLocalServer.removeServer',
                            lambda self: True)
        qlocalserver.listen('qutebrowser-test')
        with pytest.raises(ipc.AddressInUseError):
            ipc_server.listen()

    def test_successful(self, ipc_server):
        ipc_server.listen()


class TestOnError:

    def test_closed(self, ipc_server):
        ipc_server._socket = QLocalSocket()
        ipc_server._timer.timeout.disconnect()
        ipc_server._timer.start()
        ipc_server.on_error(QLocalSocket.PeerClosedError)
        assert not ipc_server._timer.isActive()

    def test_other_error(self, ipc_server, monkeypatch):
        socket = QLocalSocket()
        ipc_server._socket = socket
        monkeypatch.setattr(socket, 'error',
                            lambda: QLocalSocket.ConnectionRefusedError)
        monkeypatch.setattr(socket, 'errorString',
                            lambda: "Connection refused")
        socket.setErrorString("Connection refused.")

        with pytest.raises(ipc.Error) as excinfo:
            ipc_server.on_error(QLocalSocket.ConnectionRefusedError)

        expected = ("Error while handling IPC connection: Connection refused "
                    "(error 0)")
        assert str(excinfo.value) == expected


class TestHandleConnection:

    def test_ignored(self, ipc_server, monkeypatch):
        m = mock.Mock(spec=[])
        monkeypatch.setattr(ipc_server._server, 'nextPendingConnection', m)
        ipc_server.ignored = True
        ipc_server.handle_connection()
        assert not m.called

    def test_no_connection(self, ipc_server, caplog):
        ipc_server.handle_connection()
        assert len(caplog.records()) == 1
        record = caplog.records()[0]
        assert record.message == "No new connection to handle."

    def test_double_connection(self, qlocalsocket, ipc_server, caplog):
        ipc_server._socket = qlocalsocket
        ipc_server.handle_connection()
        message = ("Got new connection but ignoring it because we're still "
                   "handling another one.")
        assert message in [rec.message for rec in caplog.records()]

    def test_disconnected_immediately(self, ipc_server, caplog):
        socket = FakeSocket(state=QLocalSocket.UnconnectedState)
        ipc_server._server = FakeServer(socket)
        ipc_server.handle_connection()
        msg = "Socket was disconnected immediately."
        all_msgs = [r.message for r in caplog.records()]
        assert msg in all_msgs

    def test_error_immediately(self, ipc_server, caplog):
        socket = FakeSocket(error=QLocalSocket.ConnectionError)
        ipc_server._server = FakeServer(socket)

        with pytest.raises(ipc.Error) as excinfo:
            ipc_server.handle_connection()

        exc_msg = 'Error while handling IPC connection: Error string (error 7)'
        assert str(excinfo.value) == exc_msg
        msg = "We got an error immediately."
        all_msgs = [r.message for r in caplog.records()]
        assert msg in all_msgs

    def test_read_line_immediately(self, qtbot, ipc_server, caplog):
        socket = FakeSocket(data=b'{"args": ["foo"]}\n')

        ipc_server._server = FakeServer(socket)

        spy = QSignalSpy(ipc_server.got_args)
        with qtbot.waitSignal(ipc_server.got_args, raising=True):
            ipc_server.handle_connection()

        assert len(spy) == 1
        assert spy[0][0] == ['foo']

        all_msgs = [r.message for r in caplog.records()]
        assert "We can read a line immediately." in all_msgs


@pytest.yield_fixture
def connected_socket(qtbot, qlocalsocket, ipc_server):
    ipc_server.listen()
    with qtbot.waitSignal(ipc_server._server.newConnection, raising=True):
        qlocalsocket.connectToServer('qutebrowser-test')
    yield qlocalsocket
    qlocalsocket.disconnectFromServer()


def test_disconnected_without_data(qtbot, connected_socket,
                                   ipc_server, caplog):
    """Disconnect without sending data.

    This means self._socket will be None on on_disconnected.
    """
    connected_socket.disconnectFromServer()


def test_partial_line(connected_socket):
    connected_socket.write(b'foo')


@pytest.mark.parametrize('data', [
    b'\x80\n', # invalid UTF8
    b'\n',
    b'{"is this invalid json?": true\n',
    b'{"valid json without args": true}\n',
])
def test_invalid_data(qtbot, ipc_server, connected_socket, caplog, data):
    signals = [ipc_server.got_invalid_data, connected_socket.disconnected]
    with caplog.atLevel(logging.ERROR):
        with qtbot.waitSignals(signals, raising=True):
            connected_socket.write(data)
    messages = [r.message for r in caplog.records()]
    assert messages[-1] == 'Ignoring invalid IPC data.'


def test_multiline(qtbot, ipc_server, connected_socket):
    spy = QSignalSpy(ipc_server.got_args)
    error_spy = QSignalSpy(ipc_server.got_invalid_data)

    with qtbot.waitSignals([ipc_server.got_args, ipc_server.got_args],
                           raising=True):
        connected_socket.write(b'{"args": ["one"]}\n{"args": ["two"]}\n')

    assert len(spy) == 2
    assert not error_spy
    assert spy[0][0] == ['one']
    assert spy[1][0] == ['two']


class TestSendToRunningInstance:

    def test_no_server(self, caplog):
        sent = ipc.send_to_running_instance('qutebrowser-test', [])
        assert not sent
        msg = caplog.records()[-1].message
        assert msg == "No existing instance present (error 2)"

    @pytest.mark.parametrize('has_cwd', [True, False])
    @pytest.mark.posix   # Causes random trouble on Windows
    def test_normal(self, qtbot, tmpdir, ipc_server, mocker, has_cwd):
        ipc_server.listen()
        spy = QSignalSpy(ipc_server.got_args)
        raw_spy = QSignalSpy(ipc_server.got_raw)
        error_spy = QSignalSpy(ipc_server.got_invalid_data)

        with qtbot.waitSignal(ipc_server.got_args, raising=True, timeout=5000):
            with tmpdir.as_cwd():
                if not has_cwd:
                    m = mocker.patch('qutebrowser.misc.ipc.os')
                    m.getcwd.side_effect = OSError
                sent = ipc.send_to_running_instance('qutebrowser-test',
                                                    ['foo'])

        assert sent

        assert not error_spy
        expected_cwd = str(tmpdir) if has_cwd else ''

        assert len(spy) == 1
        assert spy[0] == [['foo'], expected_cwd]

        assert len(raw_spy) == 1
        assert len(raw_spy[0]) == 1
        raw_expected = {'args': ['foo'], 'version': qutebrowser.__version__}
        if has_cwd:
            raw_expected['cwd'] = str(tmpdir)
        parsed = json.loads(raw_spy[0][0].decode('utf-8'))
        assert parsed == raw_expected

    def test_socket_error(self):
        socket = FakeSocket(error=QLocalSocket.ConnectionError)
        with pytest.raises(ipc.Error) as excinfo:
            ipc.send_to_running_instance('qutebrowser-test', [], socket=socket)

        msg = "Error while writing to running instance: Error string (error 7)"
        assert str(excinfo.value) == msg

    def test_not_disconnected_immediately(self):
        socket = FakeSocket()
        ipc.send_to_running_instance('qutebrowser-test', [], socket=socket)

    def test_socket_error_no_server(self):
        socket = FakeSocket(error=QLocalSocket.ConnectionError,
                            connect_successful=False)
        with pytest.raises(ipc.Error) as excinfo:
            ipc.send_to_running_instance('qutebrowser-test', [], socket=socket)

        msg = ("Error while connecting to running instance: Error string "
               "(error 7)")
        assert str(excinfo.value) == msg


def test_timeout(qtbot, caplog, qlocalsocket, ipc_server):
    ipc_server._timer.setInterval(100)
    ipc_server.listen()

    with qtbot.waitSignal(ipc_server._server.newConnection, raising=True):
        qlocalsocket.connectToServer('qutebrowser-test')

    with caplog.atLevel(logging.ERROR):
        with qtbot.waitSignal(qlocalsocket.disconnected, raising=True):
            pass

    assert caplog.records()[-1].message == "IPC connection timed out."


@pytest.mark.parametrize('method, args', [
    pytest.mark.posix(('on_error', [0])),
    ('on_disconnected', []),
    ('on_ready_read', []),
])
def test_ipcserver_socket_none(ipc_server, caplog, method, args):
    func = getattr(ipc_server, method)
    assert ipc_server._socket is None

    with caplog.atLevel(logging.WARNING):
        func(*args)

    records = caplog.records()
    assert len(records) == 1
    msg = "In {} with None socket!".format(method)
    assert records[0].message == msg


class TestSendOrListen:

    Args = collections.namedtuple('Args', 'no_err_windows, basedir, command')

    @pytest.fixture
    def args(self):
        return self.Args(no_err_windows=True, basedir='/basedir/for/testing',
                         command=['test'])

    @pytest.fixture(autouse=True)
    def cleanup(self):
        try:
            objreg.delete('ipc-server')
        except KeyError:
            pass

    @pytest.fixture
    def qlocalserver_mock(self, mocker):
        m = mocker.patch('qutebrowser.misc.ipc.QLocalServer', autospec=True)
        m().errorString.return_value = "Error string"
        m().newConnection = stubs.FakeSignal()
        return m

    @pytest.fixture
    def qlocalsocket_mock(self, mocker):
        m = mocker.patch('qutebrowser.misc.ipc.QLocalSocket', autospec=True)
        m().errorString.return_value = "Error string"
        for attr in ['UnknownSocketError', 'UnconnectedState',
                     'ConnectionRefusedError', 'ServerNotFoundError',
                     'PeerClosedError']:
            setattr(m, attr, getattr(QLocalSocket, attr))
        return m

    @pytest.mark.posix   # Flaky on Windows
    def test_normal_connection(self, caplog, qtbot, args):
        ret_server = ipc.send_or_listen(args)
        assert isinstance(ret_server, ipc.IPCServer)
        msgs = [e.message for e in caplog.records()]
        assert "Starting IPC server..." in msgs
        objreg_server = objreg.get('ipc-server')
        assert objreg_server is ret_server

        with qtbot.waitSignal(ret_server.got_args, raising=True):
            ret_client = ipc.send_or_listen(args)

        assert ret_client is None
        ret_server.shutdown()

    def test_address_in_use_ok(self, qlocalserver_mock, qlocalsocket_mock,
                               stubs, caplog, args):
        """Test the following scenario:

        - First call to send_to_running_instance:
            -> could not connect (server not found)
        - Trying to set up a server and listen
            -> AddressInUseError
        - Second call to send_to_running_instance:
            -> success
        """
        qlocalserver_mock().listen.return_value = False
        err = QAbstractSocket.AddressInUseError
        qlocalserver_mock().serverError.return_value = err

        qlocalsocket_mock().waitForConnected.side_effect = [False, True]
        qlocalsocket_mock().error.side_effect = [
            QLocalSocket.ServerNotFoundError,
            QLocalSocket.UnknownSocketError,
            QLocalSocket.UnknownSocketError,  # error() gets called twice
        ]

        ret = ipc.send_or_listen(args)
        assert ret is None
        msgs = [e.message for e in caplog.records()]
        assert "Got AddressInUseError, trying again." in msgs

    @pytest.mark.parametrize('has_error, exc_name, exc_msg', [
        (True, 'SocketError',
            'Error while writing to running instance: Error string (error 0)'),
        (False, 'AddressInUseError',
            'Error while listening to IPC server: Error string (error 8)'),
    ])
    def test_address_in_use_error(self, qlocalserver_mock, qlocalsocket_mock,
                                  stubs, caplog, args, has_error, exc_name,
                                  exc_msg):
        """Test the following scenario:

        - First call to send_to_running_instance:
            -> could not connect (server not found)
        - Trying to set up a server and listen
            -> AddressInUseError
        - Second call to send_to_running_instance:
            -> not sent / error
        """
        qlocalserver_mock().listen.return_value = False
        err = QAbstractSocket.AddressInUseError
        qlocalserver_mock().serverError.return_value = err

        # If the second connection succeeds, we will have an error later.
        # If it fails, that's the "not sent" case above.
        qlocalsocket_mock().waitForConnected.side_effect = [False, has_error]
        qlocalsocket_mock().error.side_effect = [
            QLocalSocket.ServerNotFoundError,
            QLocalSocket.ServerNotFoundError,
            QLocalSocket.ConnectionRefusedError,
            QLocalSocket.ConnectionRefusedError,  # error() gets called twice
        ]

        with caplog.atLevel(logging.ERROR):
            with pytest.raises(ipc.Error):
                ipc.send_or_listen(args)

        msgs = [e.message for e in caplog.records()]
        error_msgs = [
            'Handling fatal misc.ipc.{} with --no-err-windows!'.format(
                exc_name),
            'title: Error while connecting to running instance!',
            'pre_text: ',
            'post_text: Maybe another instance is running but frozen?',
            'exception text: {}'.format(exc_msg),
        ]
        assert msgs[-5:] == error_msgs

    @pytest.mark.posix   # Flaky on Windows
    def test_error_while_listening(self, qlocalserver_mock, caplog, args):
        """Test an error with the first listen call."""
        qlocalserver_mock().listen.return_value = False
        err = QAbstractSocket.SocketResourceError
        qlocalserver_mock().serverError.return_value = err

        with caplog.atLevel(logging.ERROR):
            with pytest.raises(ipc.Error):
                ipc.send_or_listen(args)

        msgs = [e.message for e in caplog.records()]
        error_msgs = [
            'Handling fatal misc.ipc.ListenError with --no-err-windows!',
            'title: Error while connecting to running instance!',
            'pre_text: ',
            'post_text: Maybe another instance is running but frozen?',
            'exception text: Error while listening to IPC server: Error '
                'string (error 4)',
        ]
        assert msgs[-5:] == error_msgs
