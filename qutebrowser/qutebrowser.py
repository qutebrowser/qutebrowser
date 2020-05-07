# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Early initialization and main entry point.

qutebrowser's initialization process roughly looks like this:

- This file gets imported, either via the setuptools entry point or
  __main__.py.
- At import time, we check for the correct Python version and show an error if
  it's too old.
- The main() function in this file gets invoked
- Argument parsing takes place
- earlyinit.early_init() gets invoked to do various low-level initialization
  and checks whether all dependencies are met.
- app.run() gets called, which takes over.
  See the docstring of app.py for details.
"""

import sys
import json

import qutebrowser
try:
    from qutebrowser.misc.checkpyver import check_python_version
except ImportError:
    try:
        # python2
        from .misc.checkpyver import check_python_version
    except (SystemError, ValueError):
        # Import without module - SystemError on Python3, ValueError (?!?) on
        # Python2
        sys.stderr.write("Please don't run this script directly, do something "
                         "like   python3 -m qutebrowser   instead.\n")
        sys.stderr.flush()
        sys.exit(100)
check_python_version()

import argparse  # pylint: disable=wrong-import-order
from qutebrowser.misc import earlyinit


def get_argparser():
    """Get the argparse parser."""
    parser = argparse.ArgumentParser(prog='qutebrowser',
                                     description=qutebrowser.__description__)
    parser.add_argument('-B', '--basedir', help="Base directory for all "
                        "storage.")
    parser.add_argument('-C', '--config-py', help="Path to config.py.",
                        metavar='CONFIG')
    parser.add_argument('-V', '--version', help="Show version and quit.",
                        action='store_true')
    parser.add_argument('-s', '--set', help="Set a temporary setting for "
                        "this session.", nargs=2, action='append',
                        dest='temp_settings', default=[],
                        metavar=('OPTION', 'VALUE'))
    parser.add_argument('-r', '--restore', help="Restore a named session.",
                        dest='session')
    parser.add_argument('-R', '--override-restore', help="Don't restore a "
                        "session even if one would be restored.",
                        action='store_true')
    parser.add_argument('--target', choices=['auto', 'tab', 'tab-bg',
                                             'tab-silent', 'tab-bg-silent',
                                             'window'],
                        help="How URLs should be opened if there is already a "
                             "qutebrowser instance running.")
    parser.add_argument('--backend', choices=['webkit', 'webengine'],
                        help="Which backend to use.")
    parser.add_argument('--enable-webengine-inspector', action='store_true',
                        help="Enable the web inspector for QtWebEngine. Note "
                        "that this is a SECURITY RISK and you should not "
                        "visit untrusted websites with the inspector turned "
                        "on. See https://bugreports.qt.io/browse/QTBUG-50725 "
                        "for more details. This is not needed anymore since "
                        "Qt 5.11 where the inspector is always enabled and "
                        "secure.")

    parser.add_argument('--json-args', help=argparse.SUPPRESS)
    parser.add_argument('--temp-basedir-restarted', help=argparse.SUPPRESS)

    debug = parser.add_argument_group('debug arguments')
    debug.add_argument('-l', '--loglevel', dest='loglevel',
                       help="Set loglevel", default='info',
                       choices=['critical', 'error', 'warning', 'info',
                                'debug', 'vdebug'])
    debug.add_argument('--logfilter', type=logfilter_error,
                       help="Comma-separated list of things to be logged "
                       "to the debug log on stdout.")
    debug.add_argument('--loglines',
                       help="How many lines of the debug log to keep in RAM "
                       "(-1: unlimited).",
                       default=2000, type=int)
    debug.add_argument('-d', '--debug', help="Turn on debugging options.",
                       action='store_true')
    debug.add_argument('--json-logging', action='store_true', help="Output log"
                       " lines in JSON format (one object per line).")
    debug.add_argument('--nocolor', help="Turn off colored logging.",
                       action='store_false', dest='color')
    debug.add_argument('--force-color', help="Force colored logging",
                       action='store_true')
    debug.add_argument('--nowindow', action='store_true', help="Don't show "
                       "the main window.")
    debug.add_argument('-T', '--temp-basedir', action='store_true', help="Use "
                       "a temporary basedir.")
    debug.add_argument('--no-err-windows', action='store_true', help="Don't "
                       "show any error windows (used for tests/smoke.py).")
    debug.add_argument('--qt-arg', help="Pass an argument with a value to Qt. "
                       "For example, you can do "
                       "`--qt-arg geometry 650x555+200+300` to set the window "
                       "geometry.", nargs=2, metavar=('NAME', 'VALUE'),
                       action='append')
    debug.add_argument('--qt-flag', help="Pass an argument to Qt as flag.",
                       nargs=1, action='append')
    debug.add_argument('-D', '--debug-flag', type=debug_flag_error,
                       default=[], help="Pass name of debugging feature to be"
                       " turned on.", action='append', dest='debug_flags')
    parser.add_argument('command', nargs='*', help="Commands to execute on "
                        "startup.", metavar=':command')
    # URLs will actually be in command
    parser.add_argument('url', nargs='*', help="URLs to open on startup "
                        "(empty as a window separator).")
    return parser


def directory(arg):
    if not arg:
        raise argparse.ArgumentTypeError("Invalid empty value")


def logfilter_error(logfilter):
    """Validate logger names passed to --logfilter.

    Args:
        logfilter: A comma separated list of logger names.
    """
    from qutebrowser.utils import log
    if set(logfilter.lstrip('!').split(',')).issubset(log.LOGGER_NAMES):
        return logfilter
    else:
        raise argparse.ArgumentTypeError(
            "filters: Invalid value {} - expected a list of: {}".format(
                logfilter, ', '.join(log.LOGGER_NAMES)))


def debug_flag_error(flag):
    """Validate flags passed to --debug-flag.

    Available flags:
        debug-exit: Turn on debugging of late exit.
        pdb-postmortem: Drop into pdb on exceptions.
        no-sql-history: Don't store history items.
        no-scroll-filtering: Process all scrolling updates.
        log-requests: Log all network requests.
        log-cookies: Log cookies in cookie filter.
        log-scroll-pos: Log all scrolling changes.
        stack: Enable Chromium stack logging.
        chromium: Enable Chromium logging.
        werror: Turn Python warnings into errors.
    """
    valid_flags = ['debug-exit', 'pdb-postmortem', 'no-sql-history',
                   'no-scroll-filtering', 'log-requests', 'log-cookies',
                   'lost-focusproxy', 'log-scroll-pos', 'stack', 'chromium',
                   'werror']

    if flag in valid_flags:
        return flag
    else:
        raise argparse.ArgumentTypeError("Invalid debug flag - valid flags: {}"
                                         .format(', '.join(valid_flags)))


def main():
    parser = get_argparser()
    argv = sys.argv[1:]
    args = parser.parse_args(argv)
    if args.json_args is not None:
        # Restoring after a restart.
        # When restarting, we serialize the argparse namespace into json, and
        # construct a "fake" argparse.Namespace here based on the data loaded
        # from json.
        data = json.loads(args.json_args)
        args = argparse.Namespace(**data)
    earlyinit.early_init(args)
    # We do this imports late as earlyinit needs to be run first (because of
    # version checking and other early initialization)
    from qutebrowser import app
    return app.run(args)
