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

"""Tests for qutebrowser.misc.ipc."""

import os
import getpass
import logging
import json
import hashlib
from unittest import mock

import attr
import pytest
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtNetwork import QLocalServer, QLocalSocket, QAbstractSocket
from PyQt5.QtTest import QSignalSpy

import qutebrowser
from qutebrowser.misc import ipc
from qutebrowser.utils import standarddir, utils
from helpers import stubs


pytestmark = pytest.mark.usefixtures('qapp')


@pytest.fixture(autouse=True)
def shutdown_server():
    """If ipc.send_or_listen was called, make sure to shut server down."""
    yield
    if ipc.server is not None:
        ipc.server.shutdown()


@pytest.fixture
def ipc_server(qapp, qtbot):
    server = ipc.IPCServer('qute-test')
    yield server
    if (server._socket is not None and
            server._socket.state() != QLocalSocket.UnconnectedState):
        with qtbot.waitSignal(server._socket.disconnected, raising=False):
            server._socket.abort()
    try:
        server.shutdown()
    except ipc.Error:
        pass


@pytest.fixture
def qlocalserver(qapp):
    server = QLocalServer()
    yield server
    server.close()
    server.deleteLater()


@pytest.fixture
def qlocalsocket(qapp):
    socket = QLocalSocket()
    yield socket
    socket.disconnectFromServer()
    if socket.state() != QLocalSocket.UnconnectedState:
        socket.waitForDisconnected(1000)


@pytest.fixture(autouse=True)
def fake_runtime_dir(monkeypatch, short_tmpdir):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(short_tmpdir))
    standarddir._init_runtime(args=None)
    return short_tmpdir


class FakeSocket(QObject):

    """A stub for a QLocalSocket.

    Args:
        _can_read_line_val: The value returned for canReadLine().
        _error_val: The value returned for error().
        _state_val: The value returned for state().
        _connect_successful: The value returned for waitForConnected().
    """

    readyRead = pyqtSignal()  # noqa: N815
    disconnected = pyqtSignal()

    def __init__(self, *, error=QLocalSocket.UnknownSocketError, state=None,
                 data=None, connect_successful=True, parent=None):
        super().__init__(parent)
        self._error_val = error
        self._state_val = state
        self._data = data
        self._connect_successful = connect_successful
        self.error = stubs.FakeSignal('error', func=self._error)

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


def md5(inp):
    return hashlib.md5(inp.encode('utf-8')).hexdigest()


class TestSocketName:

    WINDOWS_TESTS = [
        (None, 'qutebrowser-testusername'),
        ('/x', 'qutebrowser-testusername-{}'.format(md5('/x'))),
    ]

    @pytest.fixture(autouse=True)
    def patch_user(self, monkeypatch):
        monkeypatch.setattr(ipc.getpass, 'getuser', lambda: 'testusername')

    @pytest.mark.parametrize('basedir, expected', WINDOWS_TESTS)
    @pytest.mark.windows
    def test_windows(self, basedir, expected):
        socketname = ipc._get_socketname(basedir)
        assert socketname == expected

    @pytest.mark.parametrize('basedir, expected', WINDOWS_TESTS)
    def test_windows_on_posix(self, basedir, expected):
        socketname = ipc._get_socketname_windows(basedir)
        assert socketname == expected

    @pytest.mark.mac
    @pytest.mark.parametrize('basedir, expected', [
        (None, 'i-{}'.format(md5('testusername'))),
        ('/x', 'i-{}'.format(md5('testusername-/x'))),
    ])
    def test_mac(self, basedir, expected):
        socketname = ipc._get_socketname(basedir)
        parts = socketname.split(os.sep)
        assert parts[-2] == 'qutebrowser'
        assert parts[-1] == expected

    @pytest.mark.linux
    @pytest.mark.parametrize('basedir, expected', [
        (None, 'ipc-{}'.format(md5('testusername'))),
        ('/x', 'ipc-{}'.format(md5('testusername-/x'))),
    ])
    def test_linux(self, basedir, fake_runtime_dir, expected):
        socketname = ipc._get_socketname(basedir)
        expected_path = str(fake_runtime_dir / 'qutebrowser' / expected)
        assert socketname == expected_path

    def test_other_unix(self):
        """Fake test for POSIX systems which aren't Linux/macOS.

        We probably would adjust the code first to make it work on that
        platform.
        """
        if utils.is_windows:
            pass
        elif utils.is_mac:
            pass
        elif utils.is_linux:
            pass
        else:
            raise Exception("Unexpected platform!")


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
        with pytest.raises(ipc.Error,
                           match="Error while removing server None!"):
            ipc_server.listen()

    def test_error(self, ipc_server, monkeypatch):
        """Simulate an error while listening."""
        monkeypatch.setattr(ipc.QLocalServer, 'removeServer',
                            lambda self: True)
        monkeypatch.setattr(ipc_server, '_socketname', None)
        with pytest.raises(ipc.ListenError):
            ipc_server.listen()

    @pytest.mark.posix
    def test_in_use(self, qlocalserver, ipc_server, monkeypatch):
        monkeypatch.setattr(ipc.QLocalServer, 'removeServer',
                            lambda self: True)
        qlocalserver.listen('qute-test')
        with pytest.raises(ipc.AddressInUseError):
            ipc_server.listen()

    def test_successful(self, ipc_server):
        ipc_server.listen()

    @pytest.mark.windows
    def test_permissions_windows(self, ipc_server):
        opts = ipc_server._server.socketOptions()
        assert opts == QLocalServer.UserAccessOption

    @pytest.mark.posix
    def test_permissions_posix(self, ipc_server):
        ipc_server.listen()
        sockfile = ipc_server._server.fullServerName()
        sockdir = os.path.dirname(sockfile)

        file_stat = os.stat(sockfile)
        dir_stat = os.stat(sockdir)

        # pylint: disable=no-member,useless-suppression
        file_owner_ok = file_stat.st_uid == os.getuid()
        dir_owner_ok = dir_stat.st_uid == os.getuid()
        # pylint: enable=no-member,useless-suppression
        file_mode_ok = file_stat.st_mode & 0o777 == 0o700
        dir_mode_ok = dir_stat.st_mode & 0o777 == 0o700

        print('sockdir: {} / owner {} / mode {:o}'.format(
            sockdir, dir_stat.st_uid, dir_stat.st_mode))
        print('sockfile: {} / owner {} / mode {:o}'.format(
            sockfile, file_stat.st_uid, file_stat.st_mode))

        assert file_owner_ok or dir_owner_ok
        assert file_mode_ok or dir_mode_ok

    @pytest.mark.posix
    def test_atime_update(self, qtbot, ipc_server):
        ipc_server._atime_timer.setInterval(500)  # We don't want to wait 6h
        ipc_server.listen()
        old_atime = os.stat(ipc_server._server.fullServerName()).st_atime_ns

        with qtbot.waitSignal(ipc_server._atime_timer.timeout, timeout=2000):
            pass

        # Make sure the timer is not singleShot
        with qtbot.waitSignal(ipc_server._atime_timer.timeout, timeout=2000):
            pass

        new_atime = os.stat(ipc_server._server.fullServerName()).st_atime_ns

        assert old_atime != new_atime

    @pytest.mark.posix
    def test_atime_update_no_name(self, qtbot, caplog, ipc_server):
        with caplog.at_level(logging.ERROR):
            ipc_server.update_atime()

        assert caplog.messages[-1] == "In update_atime with no server path!"

    @pytest.mark.posix
    def test_atime_shutdown_typeerror(self, qtbot, ipc_server):
        """This should never happen, but let's handle it gracefully."""
        ipc_server._atime_timer.timeout.disconnect(ipc_server.update_atime)
        ipc_server.shutdown()


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

        with pytest.raises(ipc.Error, match=r"Error while handling IPC "
                           r"connection: Connection refused \(error 0\)"):
            ipc_server.on_error(QLocalSocket.ConnectionRefusedError)


class TestHandleConnection:

    def test_ignored(self, ipc_server, monkeypatch):
        m = mock.Mock(spec=[])
        monkeypatch.setattr(ipc_server._server, 'nextPendingConnection', m)
        ipc_server.ignored = True
        ipc_server.handle_connection()
        m.assert_not_called()

    def test_no_connection(self, ipc_server, caplog):
        ipc_server.handle_connection()
        assert caplog.messages[-1] == "No new connection to handle."

    def test_double_connection(self, qlocalsocket, ipc_server, caplog):
        ipc_server._socket = qlocalsocket
        ipc_server.handle_connection()
        msg = ("Got new connection but ignoring it because we're still "
               "handling another one")
        assert any(message.startswith(msg) for message in caplog.messages)

    def test_disconnected_immediately(self, ipc_server, caplog):
        socket = FakeSocket(state=QLocalSocket.UnconnectedState)
        ipc_server._server = FakeServer(socket)
        ipc_server.handle_connection()
        assert "Socket was disconnected immediately." in caplog.messages

    def test_error_immediately(self, ipc_server, caplog):
        socket = FakeSocket(error=QLocalSocket.ConnectionError)
        ipc_server._server = FakeServer(socket)

        with pytest.raises(ipc.Error, match=r"Error while handling IPC "
                           r"connection: Error string \(error 7\)"):
            ipc_server.handle_connection()

        assert "We got an error immediately." in caplog.messages

    def test_read_line_immediately(self, qtbot, ipc_server, caplog):
        data = ('{{"args": ["foo"], "target_arg": "tab", '
                '"protocol_version": {}}}\n'.format(ipc.PROTOCOL_VERSION))
        socket = FakeSocket(data=data.encode('utf-8'))

        ipc_server._server = FakeServer(socket)

        with qtbot.waitSignal(ipc_server.got_args) as blocker:
            ipc_server.handle_connection()

        assert blocker.args == [['foo'], 'tab', '']
        assert "We can read a line immediately." in caplog.messages


@pytest.fixture
def connected_socket(qtbot, qlocalsocket, ipc_server):
    if utils.is_mac:
        pytest.skip("Skipping connected_socket test - "
                    "https://github.com/qutebrowser/qutebrowser/issues/1045")
    ipc_server.listen()
    with qtbot.waitSignal(ipc_server._server.newConnection):
        qlocalsocket.connectToServer('qute-test')
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


OLD_VERSION = str(ipc.PROTOCOL_VERSION - 1).encode('utf-8')
NEW_VERSION = str(ipc.PROTOCOL_VERSION + 1).encode('utf-8')


@pytest.mark.parametrize('data, msg', [
    (b'\x80\n', 'invalid utf-8'),
    (b'\n', 'invalid json'),
    (b'{"is this invalid json?": true\n', 'invalid json'),
    (b'{"valid json without args": true}\n', 'Missing args'),
    (b'{"args": []}\n', 'Missing target_arg'),
    (b'{"args": [], "target_arg": null, "protocol_version": ' + OLD_VERSION +
     b'}\n', 'incompatible version'),
    (b'{"args": [], "target_arg": null, "protocol_version": ' + NEW_VERSION +
     b'}\n', 'incompatible version'),
    (b'{"args": [], "target_arg": null, "protocol_version": "foo"}\n',
     'invalid version'),
    (b'{"args": [], "target_arg": null}\n', 'invalid version'),
])
def test_invalid_data(qtbot, ipc_server, connected_socket, caplog, data, msg):
    signals = [ipc_server.got_invalid_data, connected_socket.disconnected]
    with caplog.at_level(logging.ERROR):
        with qtbot.assertNotEmitted(ipc_server.got_args):
            with qtbot.waitSignals(signals, order='strict'):
                connected_socket.write(data)

    invalid_msg = 'Ignoring invalid IPC data from socket '
    assert caplog.messages[-1].startswith(invalid_msg)
    assert caplog.messages[-2].startswith(msg)


def test_multiline(qtbot, ipc_server, connected_socket):
    spy = QSignalSpy(ipc_server.got_args)

    data = ('{{"args": ["one"], "target_arg": "tab",'
            ' "protocol_version": {version}}}\n'
            '{{"args": ["two"], "target_arg": null,'
            ' "protocol_version": {version}}}\n'.format(
                version=ipc.PROTOCOL_VERSION))

    with qtbot.assertNotEmitted(ipc_server.got_invalid_data):
        with qtbot.waitSignals([ipc_server.got_args, ipc_server.got_args],
                               order='strict'):
            connected_socket.write(data.encode('utf-8'))

    assert len(spy) == 2
    assert spy[0] == [['one'], 'tab', '']
    assert spy[1] == [['two'], '', '']


class TestSendToRunningInstance:

    def test_no_server(self, caplog):
        sent = ipc.send_to_running_instance('qute-test', [], None)
        assert not sent
        assert caplog.messages[-1] == "No existing instance present (error 2)"

    @pytest.mark.parametrize('has_cwd', [True, False])
    @pytest.mark.linux(reason="Causes random trouble on Windows and macOS")
    def test_normal(self, qtbot, tmpdir, ipc_server, mocker, has_cwd):
        ipc_server.listen()

        with qtbot.assertNotEmitted(ipc_server.got_invalid_data):
            with qtbot.waitSignal(ipc_server.got_args,
                                  timeout=5000) as blocker:
                with qtbot.waitSignal(ipc_server.got_raw,
                                      timeout=5000) as raw_blocker:
                    with tmpdir.as_cwd():
                        if not has_cwd:
                            m = mocker.patch('qutebrowser.misc.ipc.os')
                            m.getcwd.side_effect = OSError
                        sent = ipc.send_to_running_instance(
                            'qute-test', ['foo'], None)

        assert sent

        expected_cwd = str(tmpdir) if has_cwd else ''

        assert blocker.args == [['foo'], '', expected_cwd]

        raw_expected = {'args': ['foo'], 'target_arg': None,
                        'version': qutebrowser.__version__,
                        'protocol_version': ipc.PROTOCOL_VERSION}
        if has_cwd:
            raw_expected['cwd'] = str(tmpdir)

        assert len(raw_blocker.args) == 1
        parsed = json.loads(raw_blocker.args[0].decode('utf-8'))
        assert parsed == raw_expected

    def test_socket_error(self):
        socket = FakeSocket(error=QLocalSocket.ConnectionError)
        with pytest.raises(ipc.Error, match=r"Error while writing to running "
                           r"instance: Error string \(error 7\)"):
            ipc.send_to_running_instance('qute-test', [], None, socket=socket)

    def test_not_disconnected_immediately(self):
        socket = FakeSocket()
        ipc.send_to_running_instance('qute-test', [], None, socket=socket)

    def test_socket_error_no_server(self):
        socket = FakeSocket(error=QLocalSocket.ConnectionError,
                            connect_successful=False)
        with pytest.raises(ipc.Error, match=r"Error while connecting to "
                           r"running instance: Error string \(error 7\)"):
            ipc.send_to_running_instance('qute-test', [], None, socket=socket)


@pytest.mark.not_mac(reason="https://github.com/qutebrowser/qutebrowser/"
                            "issues/975")
def test_timeout(qtbot, caplog, qlocalsocket, ipc_server):
    ipc_server._timer.setInterval(100)
    ipc_server.listen()

    with qtbot.waitSignal(ipc_server._server.newConnection):
        qlocalsocket.connectToServer('qute-test')

    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(qlocalsocket.disconnected, timeout=5000):
            pass

    assert caplog.messages[-1].startswith("IPC connection timed out")


def test_ipcserver_socket_none_readyread(ipc_server, caplog):
    assert ipc_server._socket is None
    assert ipc_server._old_socket is None
    with caplog.at_level(logging.WARNING):
        ipc_server.on_ready_read()
    msg = "In on_ready_read with None socket and old_socket!"
    assert msg in caplog.messages


@pytest.mark.posix
def test_ipcserver_socket_none_error(ipc_server, caplog):
    assert ipc_server._socket is None
    ipc_server.on_error(0)
    msg = "In on_error with None socket!"
    assert msg in caplog.messages


class TestSendOrListen:

    @attr.s
    class Args:

        no_err_windows = attr.ib()
        basedir = attr.ib()
        command = attr.ib()
        target = attr.ib()

    @pytest.fixture
    def args(self):
        return self.Args(no_err_windows=True, basedir='/basedir/for/testing',
                         command=['test'], target=None)

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
        for name in ['UnknownSocketError', 'UnconnectedState',
                     'ConnectionRefusedError', 'ServerNotFoundError',
                     'PeerClosedError']:
            setattr(m, name, getattr(QLocalSocket, name))
        return m

    @pytest.mark.linux(reason="Flaky on Windows and macOS")
    def test_normal_connection(self, caplog, qtbot, args):
        ret_server = ipc.send_or_listen(args)
        assert isinstance(ret_server, ipc.IPCServer)
        assert "Starting IPC server..." in caplog.messages
        assert ret_server is ipc.server

        with qtbot.waitSignal(ret_server.got_args):
            ret_client = ipc.send_or_listen(args)

        assert ret_client is None

    @pytest.mark.posix(reason="Unneeded on Windows")
    def test_correct_socket_name(self, args):
        server = ipc.send_or_listen(args)
        expected_dir = ipc._get_socketname(args.basedir)
        assert '/' in expected_dir
        assert server._socketname == expected_dir

    def test_address_in_use_ok(self, qlocalserver_mock, qlocalsocket_mock,
                               stubs, caplog, args):
        """Test the following scenario.

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
        assert "Got AddressInUseError, trying again." in caplog.messages

    @pytest.mark.parametrize('has_error, exc_name, exc_msg', [
        (True, 'SocketError',
         'Error while writing to running instance: Error string (error 0)'),
        (False, 'AddressInUseError',
         'Error while listening to IPC server: Error string (error 8)'),
    ])
    def test_address_in_use_error(self, qlocalserver_mock, qlocalsocket_mock,
                                  stubs, caplog, args, has_error, exc_name,
                                  exc_msg):
        """Test the following scenario.

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

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ipc.Error):
                ipc.send_or_listen(args)

        error_msgs = [
            'Handling fatal misc.ipc.{} with --no-err-windows!'.format(
                exc_name),
            '',
            'title: Error while connecting to running instance!',
            'pre_text: ',
            'post_text: Maybe another instance is running but frozen?',
            'exception text: {}'.format(exc_msg),
        ]
        assert caplog.messages == ['\n'.join(error_msgs)]

    @pytest.mark.posix(reason="Flaky on Windows")
    def test_error_while_listening(self, qlocalserver_mock, caplog, args):
        """Test an error with the first listen call."""
        qlocalserver_mock().listen.return_value = False
        err = QAbstractSocket.SocketResourceError
        qlocalserver_mock().serverError.return_value = err

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ipc.Error):
                ipc.send_or_listen(args)

        error_msgs = [
            'Handling fatal misc.ipc.ListenError with --no-err-windows!',
            '',
            'title: Error while connecting to running instance!',
            'pre_text: ',
            'post_text: Maybe another instance is running but frozen?',
            ('exception text: Error while listening to IPC server: Error '
             'string (error 4)'),
        ]
        assert caplog.messages[-1] == '\n'.join(error_msgs)


@pytest.mark.windows
@pytest.mark.mac
def test_long_username(monkeypatch):
    """See https://github.com/qutebrowser/qutebrowser/issues/888."""
    username = 'alexandercogneau'
    basedir = '/this_is_a_long_basedir'
    monkeypatch.setattr('getpass.getuser', lambda: username)
    name = ipc._get_socketname(basedir=basedir)
    server = ipc.IPCServer(name)
    expected_md5 = md5('{}-{}'.format(username, basedir))
    assert expected_md5 in server._socketname
    try:
        server.listen()
    finally:
        server.shutdown()


def test_connect_inexistent(qlocalsocket):
    """Make sure connecting to an inexistent server fails immediately.

    If this test fails, our connection logic checking for the old naming scheme
    would not work properly.
    """
    qlocalsocket.connectToServer('qute-test-inexistent')
    assert qlocalsocket.error() == QLocalSocket.ServerNotFoundError


@pytest.mark.posix
def test_socket_options_address_in_use_problem(qlocalserver, short_tmpdir):
    """Qt seems to ignore AddressInUseError when using socketOptions.

    With this test we verify this bug still exists. If it fails, we can
    probably start using setSocketOptions again.
    """
    servername = str(short_tmpdir / 'x')

    s1 = QLocalServer()
    ok = s1.listen(servername)
    assert ok

    s2 = QLocalServer()
    s2.setSocketOptions(QLocalServer.UserAccessOption)
    ok = s2.listen(servername)
    print(s2.errorString())
    # We actually would expect ok == False here - but we want the test to fail
    # when the Qt bug is fixed.
    assert ok
