# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import json
import getpass

from PyQt5.QtNetwork import QLocalSocket, QLocalServer

from qutebrowser.utils import log, objreg


SOCKETNAME = 'qutebrowser-{}'.format(getpass.getuser())
CONNECT_TIMEOUT = 100

server = None


class IPCError(Exception):

    """Exception raised when there was a problem with IPC."""


def send_to_running_instance(cmdlist):
    """Try to send a commandline to a running instance.

    Blocks for CONNECT_TIMEOUT ms.

    Args:
        cmdlist: A list to send (URLs/commands)

    Return:
        True if connecting was successful, False if no connection was made.
    """
    socket = QLocalSocket()
    socket.connectToServer(SOCKETNAME)
    connected = socket.waitForConnected(100)
    if connected:
        log.init.info("Opening in existing instance")
        line = json.dumps(cmdlist) + '\n'
        socket.writeData(line.encode('utf-8'))
        socket.waitForBytesWritten()
    else:
        if socket.error() != QLocalSocket.ConnectionRefusedError:
            raise IPCError("Error while connecting to running instance: "
                           "{}".format(socket.errorString()))
        return False


def init_server():
    global server
    server = QLocalServer()
    ok = QLocalServer.removeServer(SOCKETNAME)
    if not ok:
        raise IPCError("Error while removing server {}!".format(SOCKETNAME))
    ok = server.listen(SOCKETNAME)
    if not ok:
        raise IPCError("Error while listening to local socket: {}".format(
            server.errorString()))
    server.newConnection.connect(on_localsocket_connection)


def on_localsocket_connection(self):
    socket = self.server.nextPendingConnection()
    # FIXME timeout:
    while not socket.canReadLine():
        socket.waitForReadyRead()
    data = bytes(socket.readLine())
    args = json.loads(data.decode('utf-8'))
    app = objreg.get('app')
    app.process_args(args)
    socket.deleteLater()
