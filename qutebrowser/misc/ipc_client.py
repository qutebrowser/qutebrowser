# SPDX-FileCopyrightText: Freya Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""IPC client for sending commands to a running qutebrowser instance.

This module avoids importing Qt at module level so it can be imported in the
fast startup path before earlyinit. QLocalSocket is imported lazily inside
send_to_running_instance when needed.
"""

import os
import json
import getpass
import hashlib
import pathlib

import qutebrowser
from qutebrowser.qt.network import QLocalSocket
from qutebrowser.qt.core import QStandardPaths
from qutebrowser.utils import log, debug, utils


CONNECT_TIMEOUT = 100  # timeout for connecting/disconnecting (ms)
WRITE_TIMEOUT = 1000  # timeout for writing (ms)
PROTOCOL_VERSION = 1


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
        self.message: str = socket.errorString()

    def __str__(self):
        return "Error while {}: {} ({})".format(
            self.action, self.message, debug.qenum_key(QLocalSocket, self.code))


_FLATPAK_INFO_PATH = '/.flatpak-info'


def _get_runtime_dir(basedir, appname='qutebrowser'):
    """Get the runtime directory path using QStandardPaths.

    Uses QStandardPaths.RuntimeLocation (or TempLocation on mac/windows)
    to determine the runtime directory. Qt is imported lazily so this can
    be used in the fast startup path.

    Args:
        basedir: The --basedir argument value, or None.
        appname: The application name for the subdirectory.

    Returns:
        The runtime directory path, or None if it cannot be determined.
    """
    if basedir is not None:
        return os.path.abspath(os.path.join(basedir, 'runtime'))

    if utils.is_mac or utils.is_windows:
        # RuntimeLocation is a weird path on macOS and Windows.
        typ = QStandardPaths.StandardLocation.TempLocation
    else:
        typ = QStandardPaths.StandardLocation.RuntimeLocation

    path = QStandardPaths.writableLocation(typ)
    if not path:
        if typ == QStandardPaths.StandardLocation.TempLocation:
            return None
        # Fall back to TempLocation when RuntimeLocation is misconfigured
        path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.TempLocation)
        if not path:
            return None

    path = path.replace('/', os.sep)
    if path.split(os.sep)[-1] != appname:
        path = os.path.join(path, appname)

    # Flatpak handling
    flatpak_id = os.environ.get('FLATPAK_ID')
    if flatpak_id is None:
        info_file = pathlib.Path(_FLATPAK_INFO_PATH)
        if info_file.exists():
            # Running in Flatpak but old version without FLATPAK_ID;
            # can't reliably determine the runtime dir.
            return None

    if flatpak_id is not None:
        *parts, _ = os.path.split(path)
        path = os.path.join(*parts, 'app', flatpak_id)

    return path


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
    return os.path.join(_get_runtime_dir(basedir), filename)


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
