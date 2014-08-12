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
import configparser
from collections import OrderedDict

import pep257
from pkg_resources import load_entry_point, DistributionNotFound

# We need to do this because pyroma is braindead enough to use logging instead
# of print...
logging.basicConfig(level=logging.INFO, format='%(msg)s')

status = OrderedDict()


config = configparser.ConfigParser()
config.read('.run_checks')


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

    def _get_optional_args(checker):
        """Get a list of arguments based on a comma-separated args config."""
        try:
            return config.get(checker, 'args').split(',')
        except configparser.NoOptionError:
            return []

    def _get_flag(arg, checker, option):
        """Get a list of arguments based on a config option."""
        try:
            return ['--{}={}'.format(arg, config.get(checker, option))]
        except configparser.NoOptionError:
            return []

    args = []
    if checker == 'pylint':
        args += _get_flag('disable', 'pylint', 'disable')
        args += _get_flag('ignore', 'pylint', 'exclude')
        args += _get_optional_args('pylint')
    elif checker == 'flake8':
        args += _get_flag('ignore', 'flake8', 'disable')
        args += _get_flag('exclude', 'flake8', 'exclude')
        args += _get_optional_args('flake8')
    elif checker == 'pep257':
        args += _get_flag('ignore', 'pep257', 'disable')
        try:
            excluded = config.get('pep257', 'exclude').split(',')
        except configparser.NoOptionError:
            excluded = []
        if os.name == 'nt':
            # FIXME find a better solution
            # pep257 uses cp1252 by default on Windows, which can't handle the
            # unicode chars in some files.
            excluded += ['configdata', 'misc']
        args.append(r'--match=(?!{})\.py'.format('|'.join(excluded)))
        args += _get_optional_args('pep257')
    elif checker == 'pyroma':
        args = ['.']
    elif checker == 'check-manifest':
        args = []
    return args


def main():
    """Main entry point."""
    argv = sys.argv[:]
    check_unittest()
    check_git()
    for trg in config.get('DEFAULT', 'targets').split(','):
        print("==================== {} ====================".format(trg))
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
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
