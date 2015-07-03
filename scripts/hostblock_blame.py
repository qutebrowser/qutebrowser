#!/usr/bin/env python3
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

"""Check by which hostblock list a host was blocked."""

import sys
import io
import os
import os.path
import configparser
import urllib.request

from PyQt5.QtCore import QStandardPaths

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
from qutebrowser.browser import adblock


def main():
    """Check by which hostblock list a host was blocked."""
    if len(sys.argv) != 2:
        print("Usage: {} <host>".format(sys.argv[0]), file=sys.stderr)
        sys.exit(1)
    confdir = QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)
    confdir = confdir.replace('/', os.sep)
    if confdir.split(os.sep)[-1] != 'qutebrowser':
        confdir = os.path.join(confdir, 'qutebrowser')
    confpath = os.path.join(confdir, 'qutebrowser.conf')
    parser = configparser.ConfigParser()
    print("config path: {}".format(confpath))
    successful = parser.read(confpath, encoding='utf-8')
    if not successful:
        raise OSError("configparser did not read files successfully!")
    lists = parser['content']['host-block-lists']
    for url in lists.split(','):
        print("checking {}...".format(url))
        raw_file = urllib.request.urlopen(url)
        byte_io = io.BytesIO(raw_file.read())
        f = adblock.get_fileobj(byte_io)
        for line in f:
            if sys.argv[1] in line:
                print("FOUND {} in {}:".format(sys.argv[1], url))
                print("    " + line.rstrip())


if __name__ == '__main__':
    main()
