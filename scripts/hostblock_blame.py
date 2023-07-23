#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Check by which hostblock list a host was blocked."""

import sys
import io
import os
import os.path
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
from qutebrowser.components import hostblock
from qutebrowser.config import configdata


def main():
    """Check by which hostblock list a host was blocked."""
    if len(sys.argv) != 2:
        print("Usage: {} <host>".format(sys.argv[0]), file=sys.stderr)
        sys.exit(1)

    configdata.init()

    for url in configdata.DATA['content.blocking.hosts.lists'].default:
        print("checking {}...".format(url))
        with urllib.request.urlopen(url) as raw_file:
            byte_io = io.BytesIO(raw_file.read())
        f = hostblock.get_fileobj(byte_io)
        for line in f:
            line = line.decode('utf-8')
            if sys.argv[1] in line:
                print("FOUND {} in {}:".format(sys.argv[1], url))
                print("    " + line.rstrip())


if __name__ == '__main__':
    main()
