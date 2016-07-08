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

"""Tests for qutebrowser.misc.ipc."""

import sys
import os
import getpass
import collections
import logging
import json
import hashlib
import tempfile
import subprocess
from unittest import mock

import pytest
import py.path  # pylint: disable=no-name-in-module
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtNetwork import QLocalServer, QLocalSocket, QAbstractSocket
from PyQt5.QtTest import QSignalSpy

import qutebrowser
from qutebrowser.misc import ipc
from qutebrowser.utils import objreg, qtutils
from helpers import stubs


pytestmark = pytest.mark.usefixtures('qapp')


@pytest.yield_fixture()
def short_tmpdir():
    with tempfile.TemporaryDirectory() as tdir:
        yield py.path.local(tdir)  # pylint: disable=no-member


@pytest.yield_fixture(autouse=True)
def shutdown_server():
    """If ipc.send_or_listen was called, make sure to shut server down."""
    yield
    try:
        server = objreg.get('ipc-server')
    except KeyError:
        pass
    else:
        server.shutdown()


@pytest.yield_fixture
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


@pytest.fixture(autouse=True)
def fake_runtime_dir(monkeypatch, short_tmpdir):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(short_tmpdir))
    return short_tmpdir


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


def md5(inp):
    return hashlib.md5(inp.encode('utf-8')).hexdigest()


class TestSocketName:

    LEGACY_TESTS = [
        (None, 'qutebrowser-testusername'),
        ('/x', 'qutebrowser-testusername-{}'.format(md5('/x'))),
    ]

    POSIX_TESTS = [
        (None, 'ipc-{}'.format(md5('testusername'))),
        ('/x', 'ipc-{}'.format(md5('testusername-/x'))),
    ]

    @pytest.fixture(autouse=True)
    def patch_user(self, monkeypatch):
        monkeypatch.setattr('qutebrowser.misc.ipc.getpass.getuser',
                            lambda: 'testusername')

    @pytest.mark.parametrize('basedir, expected', LEGACY_TESTS)
    def test_legacy(self, basedir, expected):
        socketname = ipc._get_socketname(basedir, legacy=True)
        assert socketname == expected

    @pytest.mark.parametrize('basedir, expected', LEGACY_TESTS)
    @pytest.mark.windows
    def test_windows(self, basedir, expected):
        socketname = ipc._get_socketname(basedir)
        assert socketname == expected

    @pytest.mark.osx
    @pytest.mark.parametrize('basedir, expected', POSIX_TESTS)
    def test_os_x(self, basedir, expected):
        socketname = ipc._get_socketname(basedir)
        parts = socketname.split(os.sep)
        assert parts[-2] == 'qute_test'
        assert parts[-1] == expected

    @pytest.mark.linux
    @pytest.mark.parametrize('basedir, expected', POSIX_TESTS)
    def test_linux(self, basedir, fake_runtime_dir, expected):
        socketname = ipc._get_socketname(basedir)
        expected_path = str(fake_runtime_dir / 'qute_test' / expected)
        assert socketname == expected_path

    def test_other_unix(self):
        """Fake test for POSIX systems which aren't Linux/OS X.

        We probably would adjust the code first to make it work on that
        platform.
        """
        if os.name == 'nt':
            pass
        elif sys.platform == 'darwin':
            pass
        elif sys.platform.startswith('linux'):
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
        # pylint: disable=no-member,useless-suppression
        ipc_server.listen()
        sockfile = ipc_server._server.fullServerName()
        sockdir = os.path.dirname(sockfile)

        file_stat = os.stat(sockfile)
        dir_stat = os.stat(sockdir)

        file_owner_ok = file_stat.st_uid == os.getuid()
        dir_owner_ok = dir_stat.st_uid == os.getuid()
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

        assert caplog.records[-1].msg == "In update_atime with no server path!"

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
        assert caplog.records[-1].message == "No new connection to handle."

    def test_double_connection(self, qlocalsocket, ipc_server, caplog):
        ipc_server._socket = qlocalsocket
        ipc_server.handle_connection()
        msg = ("Got new connection but ignoring it because we're still "
               "handling another one")
        assert any(rec.message.startswith(msg) for rec in caplog.records)

    def test_disconnected_immediately(self, ipc_server, caplog):
        socket = FakeSocket(state=QLocalSocket.UnconnectedState)
        ipc_server._server = FakeServer(socket)
        ipc_server.handle_connection()
        msg = "Socket was disconnected immediately."
        all_msgs = [r.message for r in caplog.records]
        assert msg in all_msgs

    def test_error_immediately(self, ipc_server, caplog):
        socket = FakeSocket(error=QLocalSocket.ConnectionError)
        ipc_server._server = FakeServer(socket)

        with pytest.raises(ipc.Error) as excinfo:
            ipc_server.handle_connection()

        exc_msg = 'Error while handling IPC connection: Error string (error 7)'
        assert str(excinfo.value) == exc_msg
        msg = "We got an error immediately."
        all_msgs = [r.message for r in caplog.records]
        assert msg in all_msgs

    def test_read_line_immediately(self, qtbot, ipc_server, caplog):
        data = ('{{"args": ["foo"], "target_arg": "tab", '
                '"protocol_version": {}}}\n'.format(ipc.PROTOCOL_VERSION))
        socket = FakeSocket(data=data.encode('utf-8'))

        ipc_server._server = FakeServer(socket)

        with qtbot.waitSignal(ipc_server.got_args) as blocker:
            ipc_server.handle_connection()

        assert blocker.args == [['foo'], 'tab', '']
        all_msgs = [r.message for r in caplog.records]
        assert "We can read a line immediately." in all_msgs


@pytest.yield_fixture
def connected_socket(qtbot, qlocalsocket, ipc_server):
    if sys.platform == 'darwin':
        pytest.skip("Skipping connected_socket test - "
                    "https://github.com/The-Compiler/qutebrowser/issues/1045")
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
            with qtbot.waitSignals(signals):
                connected_socket.write(data)

    messages = [r.message for r in caplog.records]
    assert messages[-1].startswith('Ignoring invalid IPC data from socket ')
    assert messages[-2].startswith(msg)


def test_multiline(qtbot, ipc_server, connected_socket):
    spy = QSignalSpy(ipc_server.got_args)

    data = ('{{"args": ["one"], "target_arg": "tab",'
            ' "protocol_version": {version}}}\n'
            '{{"args": ["two"], "target_arg": null,'
            ' "protocol_version": {version}}}\n'.format(
                version=ipc.PROTOCOL_VERSION))

    with qtbot.assertNotEmitted(ipc_server.got_invalid_data):
        with qtbot.waitSignals([ipc_server.got_args, ipc_server.got_args]):
            connected_socket.write(data.encode('utf-8'))

    assert len(spy) == 2
    assert spy[0] == [['one'], 'tab', '']
    assert spy[1] == [['two'], '', '']


class TestSendToRunningInstance:

    def test_no_server(self, caplog):
        sent = ipc.send_to_running_instance('qute-test', [], None)
        assert not sent
        msg = caplog.records[-1].message
        assert msg == "No existing instance present (error 2)"

    @pytest.mark.parametrize('has_cwd', [True, False])
    @pytest.mark.linux(reason="Causes random trouble on Windows and OS X")
    def test_normal(self, qtbot, tmpdir, ipc_server, mocker, has_cwd):
        ipc_server.listen()
        raw_spy = QSignalSpy(ipc_server.got_raw)

        with qtbot.assertNotEmitted(ipc_server.got_invalid_data):
            with qtbot.waitSignal(ipc_server.got_args,
                                  timeout=5000) as blocker:
                with tmpdir.as_cwd():
                    if not has_cwd:
                        m = mocker.patch('qutebrowser.misc.ipc.os')
                        m.getcwd.side_effect = OSError
                    sent = ipc.send_to_running_instance('qute-test', ['foo'],
                                                        None)

            assert sent

        expected_cwd = str(tmpdir) if has_cwd else ''

        assert blocker.args == [['foo'], '', expected_cwd]

        assert len(raw_spy) == 1
        assert len(raw_spy[0]) == 1
        raw_expected = {'args': ['foo'], 'target_arg': None,
                        'version': qutebrowser.__version__,
                        'protocol_version': ipc.PROTOCOL_VERSION}
        if has_cwd:
            raw_expected['cwd'] = str(tmpdir)
        parsed = json.loads(raw_spy[0][0].decode('utf-8'))
        assert parsed == raw_expected

    def test_socket_error(self):
        socket = FakeSocket(error=QLocalSocket.ConnectionError)
        with pytest.raises(ipc.Error) as excinfo:
            ipc.send_to_running_instance('qute-test', [], None, socket=socket)

        msg = "Error while writing to running instance: Error string (error 7)"
        assert str(excinfo.value) == msg

    def test_not_disconnected_immediately(self):
        socket = FakeSocket()
        ipc.send_to_running_instance('qute-test', [], None, socket=socket)

    def test_socket_error_no_server(self):
        socket = FakeSocket(error=QLocalSocket.ConnectionError,
                            connect_successful=False)
        with pytest.raises(ipc.Error) as excinfo:
            ipc.send_to_running_instance('qute-test', [], None, socket=socket)

        msg = ("Error while connecting to running instance: Error string "
               "(error 7)")
        assert str(excinfo.value) == msg


@pytest.mark.not_osx(reason="https://github.com/The-Compiler/qutebrowser/"
                            "issues/975")
def test_timeout(qtbot, caplog, qlocalsocket, ipc_server):
    ipc_server._timer.setInterval(100)
    ipc_server.listen()

    with qtbot.waitSignal(ipc_server._server.newConnection):
        qlocalsocket.connectToServer('qute-test')

    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(qlocalsocket.disconnected, timeout=5000):
            pass

    assert caplog.records[-1].message.startswith("IPC connection timed out")


@pytest.mark.parametrize('method, args, is_warning', [
    pytest.mark.posix(('on_error', [0], False)),
    ('on_disconnected', [], False),
    ('on_ready_read', [], True),
])
def test_ipcserver_socket_none(ipc_server, caplog, method, args, is_warning):
    func = getattr(ipc_server, method)
    assert ipc_server._socket is None

    if is_warning:
        with caplog.at_level(logging.WARNING):
            func(*args)
    else:
        func(*args)

    msg = "In {} with None socket!".format(method)
    assert msg in [r.message for r in caplog.records]


class TestSendOrListen:

    Args = collections.namedtuple('Args', 'no_err_windows, basedir, command, '
                                          'target')

    @pytest.fixture
    def args(self):
        return self.Args(no_err_windows=True, basedir='/basedir/for/testing',
                         command=['test'], target=None)

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

    @pytest.yield_fixture
    def legacy_server(self, args):
        legacy_name = ipc._get_socketname(args.basedir, legacy=True)
        legacy_server = ipc.IPCServer(legacy_name)
        legacy_server.listen()
        yield legacy_server
        legacy_server.shutdown()

    @pytest.mark.linux(reason="Flaky on Windows and OS X")
    def test_normal_connection(self, caplog, qtbot, args):
        ret_server = ipc.send_or_listen(args)
        assert isinstance(ret_server, ipc.IPCServer)
        msgs = [e.message for e in caplog.records]
        assert "Starting IPC server..." in msgs
        objreg_server = objreg.get('ipc-server')
        assert objreg_server is ret_server

        with qtbot.waitSignal(ret_server.got_args):
            ret_client = ipc.send_or_listen(args)

        assert ret_client is None

    @pytest.mark.posix(reason="Unneeded on Windows")
    def test_legacy_name(self, caplog, qtbot, args, legacy_server):
        with qtbot.waitSignal(legacy_server.got_args):
            ret = ipc.send_or_listen(args)
        assert ret is None
        msgs = [e.message for e in caplog.records]
        assert "Connecting to {}".format(legacy_server._socketname) in msgs

    @pytest.mark.posix(reason="Unneeded on Windows")
    def test_stale_legacy_server(self, caplog, qtbot, args, legacy_server,
                                 ipc_server, py_proc):
        legacy_name = ipc._get_socketname(args.basedir, legacy=True)
        logging.debug('== Setting up the legacy server ==')
        cmdline = py_proc("""
            import sys

            from PyQt5.QtCore import QCoreApplication
            from PyQt5.QtNetwork import QLocalServer

            app = QCoreApplication([])

            QLocalServer.removeServer(sys.argv[1])
            server = QLocalServer()

            ok = server.listen(sys.argv[1])
            assert ok

            print(server.fullServerName())
        """)

        name = subprocess.check_output(
            [cmdline[0]] + cmdline[1] + [legacy_name])
        name = name.decode('utf-8').rstrip('\n')

        # Closing the server should not remove the FIFO yet
        assert os.path.exists(name)

        ## Setting up the new server
        logging.debug('== Setting up new server ==')
        ret_server = ipc.send_or_listen(args)
        assert isinstance(ret_server, ipc.IPCServer)

        logging.debug('== Connecting ==')
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
            QLocalSocket.ServerNotFoundError,  # legacy name
            QLocalSocket.ServerNotFoundError,
            QLocalSocket.ServerNotFoundError,  # legacy name
            QLocalSocket.UnknownSocketError,
            QLocalSocket.UnknownSocketError,  # error() gets called twice
        ]

        ret = ipc.send_or_listen(args)
        assert ret is None
        msgs = [e.message for e in caplog.records]
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
            QLocalSocket.ServerNotFoundError,  # legacy name
            QLocalSocket.ServerNotFoundError,
            QLocalSocket.ServerNotFoundError,
            QLocalSocket.ServerNotFoundError,  # legacy name
            QLocalSocket.ConnectionRefusedError,
            QLocalSocket.ConnectionRefusedError,  # error() gets called twice
        ]

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ipc.Error):
                ipc.send_or_listen(args)

        assert len(caplog.records) == 1

        error_msgs = [
            'Handling fatal misc.ipc.{} with --no-err-windows!'.format(
                exc_name),
            '',
            'title: Error while connecting to running instance!',
            'pre_text: ',
            'post_text: Maybe another instance is running but frozen?',
            'exception text: {}'.format(exc_msg),
        ]
        assert caplog.records[0].msg == '\n'.join(error_msgs)

    @pytest.mark.posix(reason="Flaky on Windows")
    def test_error_while_listening(self, qlocalserver_mock, caplog, args):
        """Test an error with the first listen call."""
        qlocalserver_mock().listen.return_value = False
        err = QAbstractSocket.SocketResourceError
        qlocalserver_mock().serverError.return_value = err

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ipc.Error):
                ipc.send_or_listen(args)

        assert len(caplog.records) == 1

        error_msgs = [
            'Handling fatal misc.ipc.ListenError with --no-err-windows!',
            '',
            'title: Error while connecting to running instance!',
            'pre_text: ',
            'post_text: Maybe another instance is running but frozen?',
            ('exception text: Error while listening to IPC server: Error '
                'string (error 4)'),
        ]
        assert caplog.records[0].msg == '\n'.join(error_msgs)


@pytest.mark.windows
@pytest.mark.osx
def test_long_username(monkeypatch):
    """See https://github.com/The-Compiler/qutebrowser/issues/888."""
    username = 'alexandercogneau'
    basedir = '/this_is_a_long_basedir'
    monkeypatch.setattr('qutebrowser.misc.ipc.standarddir.getpass.getuser',
                        lambda: username)
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


def test_socket_options_listen_problem(qlocalserver, short_tmpdir):
    """In earlier versions of Qt, listening fails when using socketOptions.

    With this test, we verify that this bug exists in the Qt version/OS
    combinations we expect it to, and doesn't exist in other versions.
    """
    servername = str(short_tmpdir / 'x')
    qlocalserver.setSocketOptions(QLocalServer.UserAccessOption)
    ok = qlocalserver.listen(servername)
    if os.name == 'nt' or qtutils.version_check('5.4'):
        assert ok
    else:
        assert not ok
        assert qlocalserver.serverError() == QAbstractSocket.HostNotFoundError
        assert qlocalserver.errorString() == 'QLocalServer::listen: Name error'


@pytest.mark.posix
@pytest.mark.skipif(not qtutils.version_check('5.4'),
                    reason="setSocketOptions is even more broken on Qt < 5.4.")
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
