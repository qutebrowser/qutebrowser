#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


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
        'too-many-positional-arguments',
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
        # __tracebackhide__
        'unnecessary-lambda-assignment',
    ]

    toxinidir = sys.argv[1]
    pythonpath = os.environ.get('PYTHONPATH', '').split(os.pathsep) + [
        toxinidir,
    ]

    args = [
        '--disable={}'.format(','.join(disabled)),
        '--ignored-modules=helpers,pytest,PyQt5',
        r'--ignore-long-lines=(<?https?://)|^ *def [a-z]',
        r'--method-rgx=[a-z_][A-Za-z0-9_]{1,100}$',
    ] + sys.argv[2:] + files
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(pythonpath)

    ret = subprocess.run(['pylint'] + args, env=env, check=False).returncode
    return ret


if __name__ == '__main__':
    sys.exit(main())
