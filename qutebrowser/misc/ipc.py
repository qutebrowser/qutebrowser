# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities for IPC with existing instances."""

import os
import time
import json
import getpass
import binascii
import hashlib
import itertools
import argparse
from typing import Optional, List

from qutebrowser.qt.core import pyqtSignal, pyqtSlot, QObject, Qt
from qutebrowser.qt.network import QLocalSocket, QLocalServer, QAbstractSocket

import qutebrowser
from qutebrowser.utils import log, usertypes, error, standarddir, utils, debug, qtutils
from qutebrowser.qt import sip


CONNECT_TIMEOUT = 100  # timeout for connecting/disconnecting
WRITE_TIMEOUT = 1000
READ_TIMEOUT = 5000
ATIME_INTERVAL = 5000 * 60  # 5 minutes
PROTOCOL_VERSION = 1


# The ipc server instance
server: Optional["IPCServer"] = None


def _get_socketname_windows(basedir: Optional[str]) -> str:
    """Get a socketname to use for Windows."""
    try:
        username = getpass.getuser()
    except ImportError:
        # getpass.getuser() first tries a couple of environment variables. If
        # none of those are set (i.e., USERNAME is missing), it tries to import
        # the "pwd" module which is unavailable on Windows.
        raise Error("Could not find username. This should only happen if "
                    "there is a bug in the application launching qutebrowser, "
                    "preventing the USERNAME environment variable from being "
                    "passed. If you know more about when this happens, please "
                    "report this to mail@qutebrowser.org.")

    parts = ['qutebrowser', username]
    if basedir is not None:
        md5 = hashlib.md5(basedir.encode('utf-8')).hexdigest()
        parts.append(md5)
    return '-'.join(parts)


def _get_socketname(basedir: Optional[str]) -> str:
    """Get a socketname to use."""
    if utils.is_windows:  # pragma: no cover
        return _get_socketname_windows(basedir)

    parts_to_hash = [getpass.getuser()]
    if basedir is not None:
        parts_to_hash.append(basedir)

    data_to_hash = '-'.join(parts_to_hash).encode('utf-8')
    md5 = hashlib.md5(data_to_hash).hexdigest()

    prefix = 'i-' if utils.is_mac else 'ipc-'
    filename = '{}{}'.format(prefix, md5)
    return os.path.join(standarddir.runtime(), filename)


class Error(Exception):

    """Base class for IPC exceptions."""


class SocketError(Error):

    """Exception raised when there was an error with a QLocalSocket.

    Args:
        code: The error code.
        message: The error message.
        action: The action which was taken when the error happened.
    """

    def __init__(self, action: str, socket: QLocalSocket) -> None:
        """Constructor.

        Args:
            action: The action which was taken when the error happened.
            socket: The QLocalSocket which has the error set.
        """
        super().__init__()
        self.action = action
        self.code: QLocalSocket.LocalSocketError = socket.error()
        self.message: str = socket.errorString()

    def __str__(self) -> str:
        return "Error while {}: {} ({})".format(
            self.action, self.message, debug.qenum_key(QLocalSocket, self.code))


class ListenError(Error):

    """Exception raised when there was a problem with listening to IPC.

    Args:
        code: The error code.
        message: The error message.
    """

    def __init__(self, local_server: QLocalServer) -> None:
        """Constructor.

        Args:
            local_server: The QLocalServer which has the error set.
        """
        super().__init__()
        self.code: QAbstractSocket.SocketError = local_server.serverError()
        self.message: str = local_server.errorString()

    def __str__(self) -> str:
        return "Error while listening to IPC server: {} ({})".format(
            self.message, debug.qenum_key(QAbstractSocket, self.code))


class AddressInUseError(ListenError):

    """Emitted when the server address is already in use."""


class IPCConnection(QObject):
    """A connection to an IPC socket.

    Multiple connections might be active in parallel.

    Attributes:
        _socket: The QLocalSocket to use.

    Signals:
        got_raw: Emitted with the connection ID and raw data from the socket.
    """

    got_raw = pyqtSignal(int, bytes)
    id_gen = itertools.count()

    def __init__(self, socket: QLocalSocket, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.conn_id = next(self.id_gen)
        log.ipc.debug("Client connected (socket {}).".format(self.conn_id))

        self._timer = usertypes.Timer(self, "ipc-timeout")
        self._timer.setInterval(READ_TIMEOUT)
        self._timer.timeout.connect(self.on_timeout)
        self._timer.start()

        self._socket: Optional[QLocalSocket] = socket
        self._socket.readyRead.connect(self.on_ready_read)

        if socket.canReadLine():
            log.ipc.debug("We can read a line immediately.")
            self.on_ready_read()

        socket.errorOccurred.connect(self.on_error)

        # FIXME:v4 Ignore needed due to overloaded signal/method in Qt 5
        socket_error = socket.error()  # type: ignore[operator,unused-ignore]
        if socket_error not in [
            QLocalSocket.LocalSocketError.UnknownSocketError,
            QLocalSocket.LocalSocketError.PeerClosedError,
        ]:
            log.ipc.debug("We got an error immediately.")
            self.on_error(socket_error)

        socket.disconnected.connect(self.on_disconnected)
        if socket.state() == QLocalSocket.LocalSocketState.UnconnectedState:
            log.ipc.debug("Socket was disconnected immediately.")
            self.on_disconnected()

    @pyqtSlot("QLocalSocket::LocalSocketError")
    def on_error(self, err: QLocalSocket.LocalSocketError) -> None:
        """Raise SocketError on fatal errors."""
        if self._socket is None:
            # Sometimes this gets called from stale sockets.
            log.ipc.debug("In on_error with None socket!")
            return
        self._timer.stop()
        log.ipc.debug(
            "Socket {}: error {}: {}".format(
                self.conn_id, self._socket.error(), self._socket.errorString()
            )
        )
        if err != QLocalSocket.LocalSocketError.PeerClosedError:
            raise SocketError(f"handling IPC connection {self.conn_id}", self._socket)

    @pyqtSlot()
    def on_disconnected(self) -> None:
        """Clean up socket when the client disconnected."""
        assert self._socket is not None
        log.ipc.debug(f"Client disconnected from socket {self.conn_id}.")
        self._timer.stop()
        self._socket.deleteLater()
        self._socket = None
        self.deleteLater()

    @pyqtSlot()
    def on_ready_read(self) -> None:
        """Read json data from the client."""
        self._timer.stop()

        while self._socket is not None and self._socket.canReadLine():
            data = self._socket.readLine().data()
            log.ipc.debug("Read from socket {}: {!r}".format(self.conn_id, data))
            self.got_raw.emit(self.conn_id, data)

        if self._socket is not None:
            self._timer.start()

    @pyqtSlot()
    def on_timeout(self) -> None:
        """Cancel the current connection if it was idle for too long."""
        assert self._socket is not None
        log.ipc.error(f"IPC connection timed out (socket {self.conn_id}).")
        self._socket.disconnectFromServer()
        if self._socket is not None:  # pragma: no cover
            # on_disconnected sets it to None
            self._socket.waitForDisconnected(CONNECT_TIMEOUT)
        if self._socket is not None:  # pragma: no cover
            # on_disconnected sets it to None
            self._socket.abort()

    @pyqtSlot(int)
    def on_invalid_data(self, conn_id: int) -> None:
        if conn_id != self.conn_id:
            return
        assert self._socket is not None
        self._socket.disconnectFromServer()


class IPCServer(QObject):

    """IPC server to which clients connect to.

    Attributes:
        ignored: Whether requests are ignored (in exception hook).
        _timer: A timer to handle timeouts.
        _server: A QLocalServer to accept new connections.
        _socketname: The socketname to use.
        _atime_timer: Timer to update the atime of the socket regularly.

    Signals:
        got_args: Emitted when there was an IPC connection and arguments were
                  passed.
        got_raw: Emitted with the raw data an IPC connection got.
        got_invalid_data: Emitted when there was invalid incoming data.
        shutting_down: IPC is shutting down.
    """

    got_args = pyqtSignal(list, str, str)
    got_raw = pyqtSignal(bytes)
    got_invalid_data = pyqtSignal(int)
    shutting_down = pyqtSignal()

    def __init__(self, socketname: str, parent: QObject = None) -> None:
        """Start the IPC server and listen to commands.

        Args:
            socketname: The socketname to use.
            parent: The parent to be used.
        """
        super().__init__(parent)
        self.ignored = False
        self._socketname = socketname

        if utils.is_windows:  # pragma: no cover
            self._atime_timer = None
        else:
            self._atime_timer = usertypes.Timer(self, 'ipc-atime')
            self._atime_timer.setInterval(ATIME_INTERVAL)
            self._atime_timer.timeout.connect(self.update_atime)
            self._atime_timer.setTimerType(Qt.TimerType.VeryCoarseTimer)

        self._server: Optional[QLocalServer] = QLocalServer(self)
        self._server.newConnection.connect(self.handle_connection)

        if utils.is_windows:  # pragma: no cover
            # As a WORKAROUND for a Qt bug, we can't use UserAccessOption on Unix. If we
            # do, we don't get an AddressInUseError anymore:
            # https://bugreports.qt.io/browse/QTBUG-48635
            #
            # Thus, we only do so on Windows, and handle permissions manually in
            # listen() on Linux.
            log.ipc.debug("Calling setSocketOptions")
            self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        else:  # pragma: no cover
            log.ipc.debug("Not calling setSocketOptions")

    def _remove_server(self) -> None:
        """Remove an existing server."""
        ok = QLocalServer.removeServer(self._socketname)
        if not ok:
            raise Error("Error while removing server {}!".format(
                self._socketname))

    def listen(self) -> None:
        """Start listening on self._socketname."""
        assert self._server is not None
        log.ipc.debug("Listening as {}".format(self._socketname))
        if self._atime_timer is not None:  # pragma: no branch
            self._atime_timer.start()
        self._remove_server()
        ok = self._server.listen(self._socketname)
        if not ok:
            if self._server.serverError() == QAbstractSocket.SocketError.AddressInUseError:
                raise AddressInUseError(self._server)
            raise ListenError(self._server)

        if not utils.is_windows:  # pragma: no cover
            # WORKAROUND for QTBUG-48635, see the comment in __init__ for details.
            try:
                os.chmod(self._server.fullServerName(), 0o700)
            except FileNotFoundError:
                # https://github.com/qutebrowser/qutebrowser/issues/1530
                # The server doesn't actually exist even if ok was reported as
                # True, so report this as an error.
                raise ListenError(self._server)

    @pyqtSlot()
    def handle_connection(self) -> None:
        """Handle a new connection to the server."""
        if self.ignored or self._server is None:
            return

        socket = qtutils.add_optional(self._server.nextPendingConnection())
        if socket is None:
            log.ipc.debug("No new connection to handle.")
            return

        conn = IPCConnection(socket, parent=self)
        conn.got_raw.connect(self.handle_data)
        self.got_invalid_data.connect(conn.on_invalid_data)
        self.shutting_down.connect(conn.on_disconnected)

    @pyqtSlot(int, bytes)
    def handle_data(self, conn_id: int, data: bytes) -> None:
        """Handle data we got from a connection."""
        try:
            decoded = data.decode('utf-8')
        except UnicodeDecodeError:
            log.ipc.error("invalid utf-8: {!r}".format(binascii.hexlify(data)))
            self._handle_invalid_data(conn_id)
            return

        log.ipc.debug("Processing: {}".format(decoded))
        try:
            json_data = json.loads(decoded)
        except ValueError:
            log.ipc.error("invalid json: {}".format(decoded.strip()))
            self._handle_invalid_data(conn_id)
            return

        for name in ['args', 'target_arg']:
            if name not in json_data:
                log.ipc.error("Missing {}: {}".format(name, decoded.strip()))
                self._handle_invalid_data(conn_id)
                return

        try:
            protocol_version = int(json_data['protocol_version'])
        except (KeyError, ValueError):
            log.ipc.error("invalid version: {}".format(decoded.strip()))
            self._handle_invalid_data(conn_id)
            return

        if protocol_version != PROTOCOL_VERSION:
            log.ipc.error("incompatible version: expected {}, got {}".format(
                PROTOCOL_VERSION, protocol_version))
            self._handle_invalid_data(conn_id)
            return

        args = json_data['args']

        target_arg = json_data['target_arg']
        if target_arg is None:
            # https://www.riverbankcomputing.com/pipermail/pyqt/2016-April/037375.html
            target_arg = ''

        cwd = json_data.get('cwd', '')
        assert cwd is not None

        self.got_args.emit(args, target_arg, cwd)

    def _handle_invalid_data(self, conn_id: int) -> None:
        """Handle invalid data we got from a QLocalSocket."""
        log.ipc.error(f"Ignoring invalid IPC data from socket {conn_id}.")
        self.got_invalid_data.emit(conn_id)

    @pyqtSlot()
    def update_atime(self) -> None:
        """Update the atime of the socket file all few hours.

        From the XDG basedir spec:

        To ensure that your files are not removed, they should have their
        access time timestamp modified at least once every 6 hours of monotonic
        time or the 'sticky' bit should be set on the file.
        """
        assert self._server is not None
        path = self._server.fullServerName()
        if not path:
            log.ipc.error("In update_atime with no server path!")
            return

        log.ipc.debug("Touching {}".format(path))

        try:
            os.utime(path)
        except OSError:
            log.ipc.exception("Failed to update IPC socket, trying to "
                              "re-listen...")
            self._server.close()
            self.listen()

    @pyqtSlot()
    def shutdown(self) -> None:
        """Shut down the IPC server cleanly."""
        if self._server is None:
            # We can get called twice when using :restart -- there, IPC is shut down
            # early to avoid processing new connections while shutting down, and then
            # we get called again when the application is about to quit.
            return

        log.ipc.debug("Shutting down IPC")
        self.shutting_down.emit()

        if self._atime_timer is not None:  # pragma: no branch
            self._atime_timer.stop()
            try:
                self._atime_timer.timeout.disconnect(self.update_atime)
            except TypeError:
                pass

        self._server.close()
        self._server.deleteLater()
        self._remove_server()
        self._server = None


def send_to_running_instance(
    socketname: int,
    command: List[str],
    target_arg: str,
    *,
    socket: Optional[QLocalSocket] = None,
) -> None:
    """Try to send a commandline to a running instance.

    Blocks for CONNECT_TIMEOUT ms.

    Args:
        socketname: The name which should be used for the socket.
        command: The command to send to the running instance.
        target_arg: --target command line argument
        socket: The socket to read data from, or None.

    Return:
        True if connecting was successful, False if no connection was made.
    """
    if socket is None:
        socket = QLocalSocket()

    log.ipc.debug("Connecting to {}".format(socketname))
    socket.connectToServer(socketname)

    connected = socket.waitForConnected(CONNECT_TIMEOUT)
    if connected:
        log.ipc.info("Opening in existing instance")
        json_data = {'args': command, 'target_arg': target_arg,
                     'version': qutebrowser.__version__,
                     'protocol_version': PROTOCOL_VERSION}
        try:
            cwd = os.getcwd()
        except OSError:
            pass
        else:
            json_data['cwd'] = cwd
        line = json.dumps(json_data) + '\n'
        data = line.encode('utf-8')
        log.ipc.debug("Writing: {!r}".format(data))
        socket.writeData(data)
        socket.waitForBytesWritten(WRITE_TIMEOUT)
        if socket.error() != QLocalSocket.LocalSocketError.UnknownSocketError:
            raise SocketError("writing to running instance", socket)
        socket.disconnectFromServer()
        if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            socket.waitForDisconnected(CONNECT_TIMEOUT)
        return True
    else:
        if socket.error() not in [QLocalSocket.LocalSocketError.ConnectionRefusedError,
                                  QLocalSocket.LocalSocketError.ServerNotFoundError]:
            raise SocketError("connecting to running instance", socket)
        log.ipc.debug("No existing instance present ({})".format(
            debug.qenum_key(QLocalSocket, socket.error())))
        return False


def display_error(exc: Exception, args: argparse.Namespace) -> None:
    """Display a message box with an IPC error."""
    error.handle_fatal_exc(
        exc, "Error while connecting to running instance!",
        no_err_windows=args.no_err_windows)


def send_or_listen(args: argparse.Namespace) -> None:
    """Send the args to a running instance or start a new IPCServer.

    Args:
        args: The argparse namespace.

    Return:
        The IPCServer instance if no running instance was detected.
        None if an instance was running and received our request.
    """
    global server
    try:
        socketname = _get_socketname(args.basedir)
        try:
            sent = send_to_running_instance(socketname, args.command,
                                            args.target)
            if sent:
                return None
            log.init.debug("Starting IPC server...")
            server = IPCServer(socketname)
            server.listen()
            return server
        except AddressInUseError:
            # This could be a race condition...
            log.init.debug("Got AddressInUseError, trying again.")
            time.sleep(0.5)
            sent = send_to_running_instance(socketname, args.command,
                                            args.target)
            if sent:
                return None
            else:
                raise
    except Error as e:
        display_error(e, args)
        raise
