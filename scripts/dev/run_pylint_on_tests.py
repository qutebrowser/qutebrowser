#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Run pylint on tests.

This is needed because pylint can't check a folder which isn't a package:
https://bitbucket.org/logilab/pylint/issue/512/
"""

import os
import sys
import os.path
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils


def main():
    """Main entry point.

    Return:
        The pylint exit status.
    """
    utils.change_cwd()
    files = []
    for dirpath, _dirnames, filenames in os.walk('tests'):
        for fn in filenames:
            if os.path.splitext(fn)[1] == '.py':
                files.append(os.path.join(dirpath, fn))
    disabled = [
        'attribute-defined-outside-init',
        'redefined-outer-name',
        'unused-argument',
        # https://bitbucket.org/logilab/pylint/issue/511/
        'undefined-variable',
    ]
    no_docstring_rgx = ['^__.*__$', '^setup$']
    args = (['--disable={}'.format(','.join(disabled)),
             '--no-docstring-rgx=({})'.format('|'.join(no_docstring_rgx))] +
            sys.argv[1:] + files)
    ret = subprocess.call(['pylint'] + args)
    return ret


if __name__ == '__main__':
    sys.exit(main())
