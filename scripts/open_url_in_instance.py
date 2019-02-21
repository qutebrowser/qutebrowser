#!/usr/bin/env python3

# This script greatly speeds up execution of qutebrowser commands when a
# qutebrowser instance already exists.  Call it in place of your system's
# qutebrowser executable.

import hashlib
import json
import os
import os.path
import socket
import subprocess
import sys

version = '1.6.0'
protocol_version = 1

m = hashlib.md5()
m.update(os.environ['USER'].encode('utf8'))
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
except OSError:
    for exec_path in reversed(os.get_exec_path()):
        try:
            subprocess.run([os.path.join(exec_path, 'qutebrowser'), *sys.argv[1:]])
            break
        except OSError:
            continue
