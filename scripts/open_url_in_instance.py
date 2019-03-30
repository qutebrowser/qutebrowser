#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2019 Gart Maddy (NoSuck) <admin@nosuck.org>

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

"""Script for faster execution.

This script greatly speeds up execution of qutebrowser commands when a
qutebrowser instance already exists.  Call it in place of your system's
qutebrowser executable.
"""

import getpass
import hashlib
import json
import os
import os.path
import qutebrowser
import socket
import subprocess
import sys

version = qutebrowser.__version__
protocol_version = 1

m = hashlib.md5()
m.update(getpass.getuser().encode('utf8'))
socket_name = 'ipc-' + m.hexdigest()

socket_path = os.path.join(os.environ['XDG_RUNTIME_DIR'], 'qutebrowser', socket_name)

command = {
    'args' : sys.argv[1:],
    'target_arg' : 'null',
    'version' : version,
    'protocol_version' : protocol_version,
    'cwd' : os.getcwd()
}

try:
    s = socket.socket(socket.AF_UNIX)
    s.connect(socket_path)
    s.sendall((json.dumps(command) + '\n').encode('utf8'))
    s.close()
except FileNotFoundError:
    os.environ['PATH'] = os.pathsep.join(reversed(os.get_exec_path()))
    subprocess.run('qutebrowser', *sys.argv[1:])
