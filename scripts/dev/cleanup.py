#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Script to clean up the mess made by Python/setuptools/PyInstaller."""

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
        if any(fnmatch.fnmatch(path, e) for e in recursive_lint):
            remove(root)


if __name__ == '__main__':
    main()
