# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Utilities for IPC with existing instances."""

import os
import sys
import time
import json
import getpass
import binascii
import hashlib

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, Qt
from PyQt5.QtNetwork import QLocalSocket, QLocalServer, QAbstractSocket

import qutebrowser
from qutebrowser.utils import (log, usertypes, error, objreg, standarddir,
                               qtutils)


CONNECT_TIMEOUT = 100
WRITE_TIMEOUT = 1000
READ_TIMEOUT = 5000
ATIME_INTERVAL = 60 * 60 * 6 * 1000  # 6 hours
PROTOCOL_VERSION = 1


def _get_socketname_legacy(basedir):
    """Legacy implementation of _get_socketname."""
    parts = ['qutebrowser', getpass.getuser()]
    if basedir is not None:
        md5 = hashlib.md5(basedir.encode('utf-8')).hexdigest()
        parts.append(md5)
    return '-'.join(parts)


def _get_socketname(basedir, legacy=False):
    """Get a socketname to use."""
    if legacy or os.name == 'nt':
        return _get_socketname_legacy(basedir)

    parts_to_hash = [getpass.getuser()]
    if basedir is not None:
        parts_to_hash.append(basedir)

    data_to_hash = '-'.join(parts_to_hash).encode('utf-8')
    md5 = hashlib.md5(data_to_hash).hexdigest()

    if sys.platform.startswith('linux'):
        target_dir = standarddir.runtime()
    else:  # pragma: no cover
        # OS X or other Unix
        target_dir = standarddir.temp()

    parts = ['ipc']
    parts.append(md5)
    return os.path.join(target_dir, '-'.join(parts))


class Error(Exception):

    """Base class for IPC exceptions."""


class SocketError(Error):

    """Exception raised when there was an error with a QLocalSocket.

    Args:
        code: The error code.
        message: The error message.
        action: The action which was taken when the error happened.
    """

    def __init__(self, action, socket):
        """Constructor.

        Args:
            action: The action which was taken when the error happened.
            socket: The QLocalSocket which has the error set.
        """
        super().__init__()
        self.action = action
        self.code = socket.error()
        self.message = socket.errorString()

    def __str__(self):
        return "Error while {}: {} (error {})".format(
            self.action, self.message, self.code)


class ListenError(Error):

    """Exception raised when there was a problem with listening to IPC.

    Args:
        code: The error code.
        message: The error message.
    """

    def __init__(self, server):
        """Constructor.

        Args:
            server: The QLocalServer which has the error set.
        """
        super().__init__()
        self.code = server.serverError()
        self.message = server.errorString()

    def __str__(self):
        return "Error while listening to IPC server: {} (error {})".format(
            self.message, self.code)


class AddressInUseError(ListenError):

    """Emitted when the server address is already in use."""


class IPCServer(QObject):

    """IPC server to which clients connect to.

    Attributes:
        ignored: Whether requests are ignored (in exception hook).
        _timer: A timer to handle timeouts.
        _server: A QLocalServer to accept new connections.
        _socket: The QLocalSocket we're currently connected to.
        _socketname: The socketname to use.
        _socketopts_ok: Set if using setSocketOptions is working with this
                        OS/Qt version.
        _atime_timer: Timer to update the atime of the socket regularily.

    Signals:
        got_args: Emitted when there was an IPC connection and arguments were
                  passed.
        got_args: Emitted with the raw data an IPC connection got.
        got_invalid_data: Emitted when there was invalid incoming data.
    """

    got_args = pyqtSignal(list, str)
    got_raw = pyqtSignal(bytes)
    got_invalid_data = pyqtSignal()

    def __init__(self, socketname, parent=None):
        """Start the IPC server and listen to commands.

        Args:
            socketname: The socketname to use.
            parent: The parent to be used.
        """
        super().__init__(parent)
        self.ignored = False
        self._socketname = socketname

        self._timer = usertypes.Timer(self, 'ipc-timeout')
        self._timer.setInterval(READ_TIMEOUT)
        self._timer.timeout.connect(self.on_timeout)

        if os.name == 'nt':  # pragma: no coverage
            self._atime_timer = None
        else:
            self._atime_timer = usertypes.Timer(self, 'ipc-atime')
            self._atime_timer.setInterval(ATIME_INTERVAL)
            self._atime_timer.timeout.connect(self.update_atime)
            self._atime_timer.setTimerType(Qt.VeryCoarseTimer)

        self._server = QLocalServer(self)
        self._server.newConnection.connect(self.handle_connection)

        self._socket = None
        self._socketopts_ok = os.name == 'nt' or qtutils.version_check('5.4')
        if self._socketopts_ok:  # pragma: no cover
            # If we use setSocketOptions on Unix with Qt < 5.4, we get a
            # NameError while listening...
            self._server.setSocketOptions(QLocalServer.UserAccessOption)

    def _remove_server(self):
        """Remove an existing server."""
        ok = QLocalServer.removeServer(self._socketname)
        if not ok:
            raise Error("Error while removing server {}!".format(
                self._socketname))

    def listen(self):
        """Start listening on self._socketname."""
        log.ipc.debug("Listening as {}".format(self._socketname))
        if self._atime_timer is not None:  # pragma: no branch
            self._atime_timer.start()
        self._remove_server()
        ok = self._server.listen(self._socketname)
        if not ok:
            if self._server.serverError() == QAbstractSocket.AddressInUseError:
                raise AddressInUseError(self._server)
            else:
                raise ListenError(self._server)
        if not self._socketopts_ok:  # pragma: no cover
            # If we use setSocketOptions on Unix with Qt < 5.4, we get a
            # NameError while listening...
            os.chmod(self._server.fullServerName(), 0o700)

    @pyqtSlot(int)
    def on_error(self, err):
        """Raise SocketError on fatal errors."""
        if self._socket is None:
            # Sometimes this gets called from stale sockets.
            msg = "In on_error with None socket!"
            if os.name == 'nt':  # pragma: no cover
                # This happens a lot on Windows, so we ignore it there.
                log.ipc.debug(msg)
            else:
                log.ipc.warn(msg)
            return
        self._timer.stop()
        log.ipc.debug("Socket error {}: {}".format(
            self._socket.error(), self._socket.errorString()))
        if err != QLocalSocket.PeerClosedError:
            raise SocketError("handling IPC connection", self._socket)

    @pyqtSlot()
    def handle_connection(self):
        """Handle a new connection to the server."""
        if self.ignored:
            return
        if self._socket is not None:
            log.ipc.debug("Got new connection but ignoring it because we're "
                          "still handling another one.")
            return
        socket = self._server.nextPendingConnection()
        if socket is None:
            log.ipc.debug("No new connection to handle.")
            return
        log.ipc.debug("Client connected.")
        self._timer.start()
        self._socket = socket
        socket.readyRead.connect(self.on_ready_read)
        if socket.canReadLine():
            log.ipc.debug("We can read a line immediately.")
            self.on_ready_read()
        socket.error.connect(self.on_error)
        if socket.error() not in (QLocalSocket.UnknownSocketError,
                                  QLocalSocket.PeerClosedError):
            log.ipc.debug("We got an error immediately.")
            self.on_error(socket.error())
        socket.disconnected.connect(self.on_disconnected)
        if socket.state() == QLocalSocket.UnconnectedState:
            log.ipc.debug("Socket was disconnected immediately.")
            self.on_disconnected()

    @pyqtSlot()
    def on_disconnected(self):
        """Clean up socket when the client disconnected."""
        log.ipc.debug("Client disconnected.")
        self._timer.stop()
        if self._socket is None:
            log.ipc.warn("In on_disconnected with None socket!")
        else:
            self._socket.deleteLater()
            self._socket = None
        # Maybe another connection is waiting.
        self.handle_connection()

    def _handle_invalid_data(self):
        """Handle invalid data we got from a QLocalSocket."""
        log.ipc.error("Ignoring invalid IPC data.")
        self.got_invalid_data.emit()
        self._socket.error.connect(self.on_error)
        self._socket.disconnectFromServer()

    @pyqtSlot()
    def on_ready_read(self):
        """Read json data from the client."""
        if self._socket is None:
            # This happens when doing a connection while another one is already
            # active for some reason.
            log.ipc.warn("In on_ready_read with None socket!")
            return
        self._timer.start()
        while self._socket is not None and self._socket.canReadLine():
            data = bytes(self._socket.readLine())
            self.got_raw.emit(data)
            log.ipc.debug("Read from socket: {}".format(data))

            try:
                decoded = data.decode('utf-8')
            except UnicodeDecodeError:
                log.ipc.error("invalid utf-8: {}".format(
                    binascii.hexlify(data)))
                self._handle_invalid_data()
                return

            log.ipc.debug("Processing: {}".format(decoded))
            try:
                json_data = json.loads(decoded)
            except ValueError:
                log.ipc.error("invalid json: {}".format(decoded.strip()))
                self._handle_invalid_data()
                return

            try:
                args = json_data['args']
            except KeyError:
                log.ipc.error("no args: {}".format(decoded.strip()))
                self._handle_invalid_data()
                return

            try:
                protocol_version = int(json_data['protocol_version'])
            except (KeyError, ValueError):
                log.ipc.error("invalid version: {}".format(decoded.strip()))
                self._handle_invalid_data()
                return

            if protocol_version != PROTOCOL_VERSION:
                log.ipc.error("incompatible version: expected {}, "
                              "got {}".format(
                                  PROTOCOL_VERSION, protocol_version))
                self._handle_invalid_data()
                return

            cwd = json_data.get('cwd', None)
            self.got_args.emit(args, cwd)

    @pyqtSlot()
    def on_timeout(self):
        """Cancel the current connection if it was idle for too long."""
        log.ipc.error("IPC connection timed out.")
        self._socket.close()

    @pyqtSlot()
    def update_atime(self):
        """Update the atime of the socket file all few hours.

        From the XDG basedir spec:

        To ensure that your files are not removed, they should have their
        access time timestamp modified at least once every 6 hours of monotonic
        time or the 'sticky' bit should be set on the file.
        """
        path = self._server.fullServerName()
        if not path:
            log.ipc.error("In update_atime with no server path!")
            return
        os.utime(path)

    def shutdown(self):
        """Shut down the IPC server cleanly."""
        if self._socket is not None:
            self._socket.deleteLater()
            self._socket = None
        self._timer.stop()
        if self._atime_timer is not None:  # pragma: no branch
            self._atime_timer.stop()
            try:
                self._atime_timer.timeout.disconnect(self.update_atime)
            except TypeError:
                pass
        self._server.close()
        self._server.deleteLater()
        self._remove_server()


def _has_legacy_server(name):
    """Check if there is a legacy server.

    Args:
        name: The name to try to connect to.

    Return:
        True if there is a server with the given name, False otherwise.
    """
    socket = QLocalSocket()
    log.ipc.debug("Trying to connect to {}".format(name))
    socket.connectToServer(name)

    err = socket.error()

    if err != QLocalSocket.UnknownSocketError:
        log.ipc.debug("Socket error: {} ({})".format(
            socket.errorString(), err))

    os_x_fail = (sys.platform == 'darwin' and
                 socket.errorString() == 'QLocalSocket::connectToServer: '
                                         'Unknown error 38')

    if err not in [QLocalSocket.ServerNotFoundError,
                   QLocalSocket.ConnectionRefusedError] and not os_x_fail:
        return True

    socket.disconnectFromServer()
    if socket.state() != QLocalSocket.UnconnectedState:
        socket.waitForDisconnected(100)
    return False


def send_to_running_instance(socketname, command, *, legacy_name=None,
                             socket=None):
    """Try to send a commandline to a running instance.

    Blocks for CONNECT_TIMEOUT ms.

    Args:
        socketname: The name which should be used for the socket.
        command: The command to send to the running instance.
        socket: The socket to read data from, or None.
        legacy_name: The legacy name to first try to connect to.

    Return:
        True if connecting was successful, False if no connection was made.
    """
    if socket is None:
        socket = QLocalSocket()

    if (legacy_name is not None and
            _has_legacy_server(legacy_name)):
        name_to_use = legacy_name
    else:
        name_to_use = socketname

    log.ipc.debug("Connecting to {}".format(name_to_use))
    socket.connectToServer(name_to_use)

    connected = socket.waitForConnected(100)
    if connected:
        log.ipc.info("Opening in existing instance")
        json_data = {'args': command, 'version': qutebrowser.__version__,
                     'protocol_version': PROTOCOL_VERSION}
        try:
            cwd = os.getcwd()
        except OSError:
            pass
        else:
            json_data['cwd'] = cwd
        line = json.dumps(json_data) + '\n'
        data = line.encode('utf-8')
        log.ipc.debug("Writing: {}".format(data))
        socket.writeData(data)
        socket.waitForBytesWritten(WRITE_TIMEOUT)
        if socket.error() != QLocalSocket.UnknownSocketError:
            raise SocketError("writing to running instance", socket)
        else:
            socket.disconnectFromServer()
            if socket.state() != QLocalSocket.UnconnectedState:
                socket.waitForDisconnected(100)
            return True
    else:
        if socket.error() not in (QLocalSocket.ConnectionRefusedError,
                                  QLocalSocket.ServerNotFoundError):
            raise SocketError("connecting to running instance", socket)
        else:
            log.ipc.debug("No existing instance present (error {})".format(
                socket.error()))
            return False


def display_error(exc, args):
    """Display a message box with an IPC error."""
    error.handle_fatal_exc(
        exc, args, "Error while connecting to running instance!",
        post_text="Maybe another instance is running but frozen?")


def send_or_listen(args):
    """Send the args to a running instance or start a new IPCServer.

    Args:
        args: The argparse namespace.

    Return:
        The IPCServer instance if no running instance was detected.
        None if an instance was running and received our request.
    """
    socketname = _get_socketname(args.basedir)
    legacy_socketname = _get_socketname(args.basedir, legacy=True)
    try:
        try:
            sent = send_to_running_instance(socketname, args.command,
                                            legacy_name=legacy_socketname)
            if sent:
                return None
            log.init.debug("Starting IPC server...")
            server = IPCServer(socketname)
            server.listen()
            objreg.register('ipc-server', server)
            return server
        except AddressInUseError as e:
            # This could be a race condition...
            log.init.debug("Got AddressInUseError, trying again.")
            time.sleep(0.5)
            sent = send_to_running_instance(socketname, args.command,
                                            legacy_name=legacy_socketname)
            if sent:
                return None
            else:
                raise
    except Error as e:
        display_error(e, args)
        raise
