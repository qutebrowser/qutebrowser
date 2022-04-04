#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Run pylint on tests.

This is needed because pylint can't check a folder which isn't a package:
https://bitbucket.org/logilab/pylint/issue/512/
"""

import os
import os.path
import sys
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
        # pytest fixtures
        'redefined-outer-name',
        'unused-argument',
        'too-many-arguments',
        # things which are okay in tests
        'missing-docstring',
        'protected-access',
        'len-as-condition',
        'compare-to-empty-string',
        'pointless-statement',
        'use-implicit-booleaness-not-comparison',
        # directories without __init__.py...
        'import-error',
        # tests/helpers imports
        'wrong-import-order',
    ]

    toxinidir = sys.argv[1]
    pythonpath = os.environ.get('PYTHONPATH', '').split(os.pathsep) + [
        toxinidir,
    ]

    args = [
        '--disable={}'.format(','.join(disabled)),
        '--ignored-modules=helpers,pytest,PyQt5',
        r'--ignore-long-lines=(<?https?://|^# Copyright 201\d)|^ *def [a-z]',
        r'--method-rgx=[a-z_][A-Za-z0-9_]{1,100}$',
    ] + sys.argv[2:] + files
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(pythonpath)

    ret = subprocess.run(['pylint'] + args, env=env, check=False).returncode
    return ret


if __name__ == '__main__':
    sys.exit(main())
