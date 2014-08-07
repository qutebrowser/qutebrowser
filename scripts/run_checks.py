#!/usr/bin/python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

# pylint: disable=broad-except

""" Run different codecheckers over a codebase.

Runs flake8, pylint, pep257, a CRLF/whitespace/conflict-checker and
pyroma/check-manifest by default.

Module attributes:
    status: An OrderedDict for return status values.
    option: A dictionary with options.
"""

import sys
import subprocess
import os
import os.path
import unittest
import logging
import tokenize
from collections import OrderedDict

try:
    import pep257
except ImportError:
    do_check_257 = False
else:
    do_check_257 = True
from pkg_resources import load_entry_point, DistributionNotFound

# We need to do this because pyroma is braindead enough to use logging instead
# of print...
logging.basicConfig(level=logging.INFO, format='%(msg)s')

status = OrderedDict()

options = {
    'targets': ['qutebrowser', 'scripts'],
    'disable': {
        'pep257': [
            'D102',  # Docstring missing, will be handled by others
            'D209',  # Blank line before closing """ (removed from PEP257)
            'D402',  # First line should not be function's signature
                     # (false-positives)
        ],
    },
    'exclude': [],
    'exclude_pep257': ['test_*', 'ez_setup'],
    'other': {
        'pylint': ['--output-format=colorized', '--reports=no',
                   '--rcfile=.pylintrc',
                   '--load-plugins=pylint_checkers.config,'
                   'pylint_checkers.crlf,'
                   'pylint_checkers.modeline,'
                   'pylint_checkers.settrace'],
        'flake8': ['--config=.flake8'],
    },
}

if os.name == 'nt':
    # pep257 uses cp1252 by default on Windows, which can't handle the unicode
    # chars in some files.
    options['exclude_pep257'] += ['configdata.py', 'misc.py']


def run(name, target=None, args=None):
    """Run a checker via distutils with optional args.

    Arguments:
        name: Name of the checker/binary
        target: The package to check
        args: Option list of arguments to pass
    """
    # pylint: disable=too-many-branches
    if name == 'pylint':
        scriptdir = os.path.abspath(os.path.dirname(__file__))
        if 'PYTHONPATH' in os.environ:
            old_pythonpath = os.environ['PYTHONPATH']
            os.environ['PYTHONPATH'] += os.pathsep + scriptdir
        else:
            old_pythonpath = None
            os.environ['PYTHONPATH'] = scriptdir
    sys.argv = [name]
    if target is None:
        status_key = name
    else:
        status_key = '{}_{}'.format(name, target)
        args.append(target)
    if args is not None:
        sys.argv += args
    print("------ {} ------".format(name))
    try:
        ep = load_entry_point(name, 'console_scripts', name)
        ep()
    except SystemExit as e:
        status[status_key] = e
    except DistributionNotFound:
        if args is None:
            args = []
        try:
            status[status_key] = subprocess.call([name] + args)
        except FileNotFoundError as e:
            print('{}: {}'.format(e.__class__.__name__, e))
            status[status_key] = None
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        status[status_key] = None
    if name == 'pylint':
        if old_pythonpath is not None:
            os.environ['PYTHONPATH'] = old_pythonpath
        else:
            del os.environ['PYTHONPATH']
    print()


def check_pep257(target, args=None):
    """Run pep257 checker with args passed."""
    sys.argv = ['pep257', target]
    if args is not None:
        sys.argv += args
    print("------ pep257 ------")
    try:
        status['pep257_' + target] = pep257.main(*pep257.parse_options())
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        status['pep257_' + target] = None
    print()


def check_unittest():
    """Run the unittest checker."""
    print("==================== unittest ====================")
    suite = unittest.TestLoader().discover('.')
    result = unittest.TextTestRunner().run(suite)
    print()
    status['unittest'] = result.wasSuccessful()


def check_git():
    """Check for uncommited git files.."""
    print("==================== git ====================")
    if not os.path.isdir(".git"):
        print("No .git dir, ignoring")
        status['git'] = False
        print()
        return
    untracked = []
    gitst = subprocess.check_output(['git', 'status', '--porcelain'])
    gitst = gitst.decode('UTF-8').strip()
    for line in gitst.splitlines():
        s, name = line.split(maxsplit=1)
        if s == '??':
            untracked.append(name)
    if untracked:
        status['git'] = False
        print("Untracked files:")
        print('\n'.join(untracked))
    else:
        status['git'] = True
    print()


def check_vcs_conflict(target):
    """Check VCS conflict markers."""
    print("------ VCS conflict markers ------")
    try:
        ok = True
        for (dirpath, _dirnames, filenames) in os.walk(target):
            for name in (e for e in filenames if e.endswith('.py')):
                fn = os.path.join(dirpath, name)
                with tokenize.open(fn) as f:
                    for line in f:
                        if any(line.startswith(c * 7) for c in '<>=|'):
                            print("Found conflict marker in {}".format(fn))
                            ok = False
        status['vcs_' + target] = ok
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        status['vcs_' + target] = None
    print()


def _get_args(checker):
    """Construct the arguments for a given checker.

    Return:
        A list of commandline arguments.
    """
    # pylint: disable=too-many-branches
    args = []
    if checker == 'pylint':
        try:
            args += ['--disable=' + ','.join(options['disable']['pylint'])]
        except KeyError:
            pass
        if options['exclude']:
            try:
                args += ['--ignore=' + ','.join(options['exclude'])]
            except KeyError:
                pass
        try:
            args += options['other']['pylint']
        except KeyError:
            pass
    elif checker == 'flake8':
        try:
            args += ['--ignore=' + ','.join(options['disable']['flake8'])]
        except KeyError:
            pass
        if options['exclude']:
            try:
                args += ['--exclude=' + ','.join(options['exclude'])]
            except KeyError:
                pass
        try:
            args += options['other']['flake8']
        except KeyError:
            pass
    elif checker == 'pep257':
        args = []
        try:
            args += ['--ignore=' + ','.join(options['disable']['pep257'])]
        except KeyError:
            pass
        try:
            args += [r'--match=(?!{}).*\.py'.format('|'.join(
                options['exclude'] + options['exclude_pep257']))]
        except KeyError:
            pass
        try:
            args += options['other']['pep257']
        except KeyError:
            pass
    elif checker == 'pyroma':
        args = ['.']
    elif checker == 'check-manifest':
        args = []
    return args


argv = sys.argv[:]
check_unittest()
check_git()
for trg in options['targets']:
    print("==================== {} ====================".format(trg))
    if do_check_257:
        check_pep257(trg, _get_args('pep257'))
    for chk in ('pylint', 'flake8'):
        # FIXME what the hell is the flake8 exit status?
        run(chk, trg, _get_args(chk))
    check_vcs_conflict(trg)

if '--setup' in argv:
    print("==================== Setup checks ====================")
    for chk in ('pyroma', 'check-manifest'):
        run(chk, args=_get_args(chk))

print("Exit status values:")
for (k, v) in status.items():
    print('  {} - {}'.format(k, v))

if all(val in (True, 0) for val in status):
    sys.exit(0)
else:
    sys.exit(1)
