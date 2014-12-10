#!/usr/bin/env python3
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
import argparse
import collections
import functools
import contextlib
import traceback

import pep257


sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from scripts import utils


# We need to do this because pyroma is braindead enough to use logging instead
# of print...
logging.basicConfig(level=logging.INFO, format='%(msg)s')


config = configparser.ConfigParser()


@contextlib.contextmanager
def _adjusted_pythonpath(name):
    """Adjust PYTHONPATH for pylint."""
    if name == 'pylint':
        scriptdir = os.path.abspath(os.path.dirname(__file__))
        if 'PYTHONPATH' in os.environ:
            old_pythonpath = os.environ['PYTHONPATH']
            os.environ['PYTHONPATH'] += os.pathsep + scriptdir
        else:
            old_pythonpath = None
            os.environ['PYTHONPATH'] = scriptdir
    yield
    if name == 'pylint':
        if old_pythonpath is not None:
            os.environ['PYTHONPATH'] = old_pythonpath
        else:
            del os.environ['PYTHONPATH']


def run(name, target=None):
    """Run a checker via distutils with optional args.

    Arguments:
        name: Name of the checker/binary
        target: The package to check
    """
    # pylint: disable=too-many-branches
    args = _get_args(name)
    if target is not None:
        args.append(target)
    with _adjusted_pythonpath(name):
        try:
            status = subprocess.call([name] + args)
        except OSError:
            traceback.print_exc()
            status = None
    print()
    return status


def check_pep257(target):
    """Run pep257 checker with args passed."""
    args = _get_args('pep257')
    sys.argv = ['pep257', target]
    if args is not None:
        sys.argv += args
    try:
        status = pep257.main(*pep257.parse_options())
        print()
        return status
    except Exception:
        traceback.print_exc()
        return None


def check_unittest():
    """Run the unittest checker."""
    suite = unittest.TestLoader().discover('.')
    result = unittest.TextTestRunner().run(suite)
    print()
    return result.wasSuccessful()


def check_git():
    """Check for uncommited git files.."""
    if not os.path.isdir(".git"):
        print("No .git dir, ignoring")
        print()
        return False
    untracked = []
    changed = []
    gitst = subprocess.check_output(['git', 'status', '--porcelain'])
    gitst = gitst.decode('UTF-8').strip()
    for line in gitst.splitlines():
        s, name = line.split(maxsplit=1)
        if s == '??' and name != '.venv/':
            untracked.append(name)
        elif s == 'M':
            changed.append(name)
    status = True
    if untracked:
        status = False
        utils.print_col("Untracked files:", 'red')
        print('\n'.join(untracked))
    if changed:
        status = False
        utils.print_col("Uncommited changes:", 'red')
        print('\n'.join(changed))
    print()
    return status


def check_vcs_conflict(target):
    """Check VCS conflict markers."""
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
        print()
        return ok
    except Exception:
        traceback.print_exc()
        return None


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
        plugins = []
        for plugin in config.get('pylint', 'plugins').split(','):
            plugins.append('pylint_checkers.{}'.format(plugin))
        args.append('--load-plugins={}'.format(','.join(plugins)))
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
            # https://github.com/The-Compiler/qutebrowser/issues/105
            excluded += ['configdata', 'misc']
        args.append(r'--match=(?!{})\.py'.format('|'.join(excluded)))
        args += _get_optional_args('pep257')
    elif checker == 'pyroma':
        args = ['.']
    elif checker == 'check-manifest':
        args = []
    return args


def _get_checkers():
    """Get a dict of checkers we need to execute."""
    # "Static" checkers
    checkers = collections.OrderedDict([
        ('global', collections.OrderedDict([
            ('unittest', check_unittest),
            ('git', check_git),
        ])),
        ('setup', collections.OrderedDict([
            ('pyroma', functools.partial(run, 'pyroma')),
            ('check-manifest', functools.partial(run, 'check-manifest')),
        ])),
    ])
    # "Dynamic" checkers which exist once for each target.
    for target in config.get('DEFAULT', 'targets').split(','):
        checkers[target] = collections.OrderedDict([
            ('pep257', functools.partial(check_pep257, target)),
            ('flake8', functools.partial(run, 'flake8', target)),
            ('vcs', functools.partial(check_vcs_conflict, target)),
            ('pylint', functools.partial(run, 'pylint', target)),
        ])
    return checkers


def _checker_enabled(args, group, name):
    """Check if a named checker is enabled."""
    if args.checkers == 'all':
        if not args.setup and group == 'setup':
            return False
        else:
            return True
    else:
        return name in args.checkers.split(',')


def _parse_args():
    """Parse commandline args via argparse."""
    parser = argparse.ArgumentParser(description='Run various checkers.')
    parser.add_argument('-s', '--setup', help="Run additional setup checks",
                        action='store_true')
    parser.add_argument('-q', '--quiet',
                        help="Don't print unnecessary headers.",
                        action='store_true')
    parser.add_argument('checkers', help="Checkers to run (or 'all')",
                        default='all', nargs='?')
    return parser.parse_args()


def main():
    """Main entry point."""
    utils.change_cwd()
    read_files = config.read('.run_checks')
    if not read_files:
        raise OSError("Could not read config!")
    exit_status = collections.OrderedDict()
    exit_status_bool = {}

    args = _parse_args()
    checkers = _get_checkers()

    groups = ['global']
    groups += config.get('DEFAULT', 'targets').split(',')
    groups.append('setup')

    for group in groups:
        print()
        utils.print_title(group)
        for name, func in checkers[group].items():
            if _checker_enabled(args, group, name):
                utils.print_subtitle(name)
                status = func()
                key = '{}_{}'.format(group, name)
                exit_status[key] = status
                if name == 'flake8':
                    # pyflakes uses True for errors and False for ok.
                    exit_status_bool[key] = not status
                elif isinstance(status, bool):
                    exit_status_bool[key] = status
                else:
                    # sys.exit(0) means no problems -> True, anything != 0
                    # means problems.
                    exit_status_bool[key] = (status == 0)
            elif not args.quiet:
                utils.print_subtitle(name)
                utils.print_col("Checker disabled.", 'blue')
    print()
    utils.print_col("Exit status values:", 'yellow')
    for (k, v) in exit_status.items():
        ok = exit_status_bool[k]
        color = 'green' if ok else 'red'
        utils.print_col(
            '    {} - {} ({})'.format(k, 'ok' if ok else 'FAIL', v), color)
    if all(exit_status_bool.values()):
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
