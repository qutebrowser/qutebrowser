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
m.update(bytes(os.getenv('USER'), 'utf8'))
socket_name = 'ipc-' + m.hexdigest()

socket_path = os.path.join(os.getenv('XDG_RUNTIME_DIR'), 'qutebrowser', socket_name)

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
    s.sendall(bytes(json.dumps(command) + '\n', 'utf8'))
    s.close()
except Exception as e:
    print(e, file=sys.stderr)
    subprocess.run(['/usr/bin/qutebrowser', *sys.argv[1:]])
