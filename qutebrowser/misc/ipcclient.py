# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities for IPCClient with existing instances."""

import os
import json
import getpass
import hashlib

from qutebrowser.qt.network import QLocalSocket

import qutebrowser
from qutebrowser.utils import log, error, standarddir, utils, debug


CONNECT_TIMEOUT = 100  # timeout for connecting/disconnecting
WRITE_TIMEOUT = 1000
READ_TIMEOUT = 5000
ATIME_INTERVAL = 5000 * 60  # 5 minutes
PROTOCOL_VERSION = 1


def _get_socketname_windows(basedir):
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


def _get_socketname(basedir):
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

    def __init__(self, action, socket):
        """Constructor.

        Args:
            action: The action which was taken when the error happened.
            socket: The QLocalSocket which has the error set.
        """
        super().__init__()
        self.action = action
        self.code: QLocalSocket.LocalSocketError = socket.error()
        self.message: str = socket.errorString()

    def __str__(self):
        return "Error while {}: {} ({})".format(
            self.action, self.message, debug.qenum_key(QLocalSocket, self.code))


def send_to_running_instance(socketname, command, target_arg, *, socket=None):
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


def display_error(exc, args):
    """Display a message box with an IPC error."""
    error.handle_fatal_exc(
        exc, "Error while connecting to running instance!",
        no_err_windows=args.no_err_windows)


def send(args):
    """send a message to IPC Server."""
    socketname = _get_socketname(args.basedir)
    try:
        sent = send_to_running_instance(socketname, args.command,
                                        args.target)
        if sent:
            return True
        return False

    except Error as e:
        display_error(e, args)
        raise e
