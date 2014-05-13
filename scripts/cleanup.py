#!/usr/bin/python
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

"""Script to clean up the mess made by Python/setuptools/cx_Freeze."""

import os
import os.path
import sys
import glob
import shutil
from fnmatch import fnmatch


recursive_lint = ['__pycache__', '*.pyc']
lint = ['build', 'pkg/pkg', 'pkg/qutebrowser-*.pkg.tar.xz', 'pkg/src',
        'pkg/qutebrowser', 'qutebrowser.egg-info', 'setuptools-*.egg',
        'setuptools-*.zip']



def remove(path):
    if os.path.isdir(path):
        print("rm -r '{}'".format(path))
        if not '--dry-run' in sys.argv: shutil.rmtree(path)
    else:
        print("rm '{}'".format(path))
        if not '--dry-run' in sys.argv: os.remove(path)


for elem in lint:
    for f in glob.glob(elem):
        remove(f)


for root, dirs, files in os.walk(os.getcwd()):
    if any([fnmatch(os.path.basename(root), e) for e in recursive_lint]):
        remove(root)
