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

"""Script to clean up the mess made by Python/setuptools/cx_Freeze."""

import os
import os.path
import sys
import glob
import shutil
import fnmatch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                os.pardir))

from scripts import utils


recursive_lint = ('__pycache__', '*.pyc')
lint = ('build', 'dist', 'pkg/pkg', 'pkg/qutebrowser-*.pkg.tar.xz', 'pkg/src',
        'pkg/qutebrowser', 'qutebrowser.egg-info', 'setuptools-*.egg',
        'setuptools-*.zip', 'doc/qutebrowser.asciidoc', 'doc/*.html',
        'doc/qutebrowser.1', 'README.html', 'qutebrowser/html/doc')


def remove(path):
    """Remove either a file or directory unless --dry-run is given."""
    if os.path.isdir(path):
        print("rm -r '{}'".format(path))
        if '--dry-run' not in sys.argv:
            shutil.rmtree(path)
    else:
        print("rm '{}'".format(path))
        if '--dry-run' not in sys.argv:
            os.remove(path)


def main():
    """Clean up lint in the current dir."""
    utils.change_cwd()
    for elem in lint:
        for f in glob.glob(elem):
            remove(f)

    for root, _dirs, _files in os.walk(os.getcwd()):
        path = os.path.basename(root)
        if any([fnmatch.fnmatch(path, e) for e in recursive_lint]):
            remove(root)


if __name__ == '__main__':
    main()
