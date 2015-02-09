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

"""Early initialization and main entry point."""

import sys

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

import argparse
from qutebrowser.misc import earlyinit


def get_argparser():
    """Get the argparse parser."""
    parser = argparse.ArgumentParser("usage: qutebrowser",
                                     description=qutebrowser.__description__)
    parser.add_argument('-c', '--confdir', help="Set config directory (empty "
                        "for no config storage)")
    parser.add_argument('-V', '--version', help="Show version and quit.",
                        action='store_true')
    debug = parser.add_argument_group('debug arguments')
    debug.add_argument('-l', '--loglevel', dest='loglevel',
                       help="Set loglevel", default='info')
    debug.add_argument('--logfilter',
                       help="Comma-separated list of things to be logged "
                       "to the debug log on stdout.")
    debug.add_argument('--loglines',
                       help="How many lines of the debug log to keep in RAM "
                       "(-1: unlimited).",
                       default=2000, type=int)
    debug.add_argument('--debug', help="Turn on debugging options.",
                       action='store_true')
    debug.add_argument('--nocolor', help="Turn off colored logging.",
                       action='store_false', dest='color')
    debug.add_argument('--harfbuzz', choices=['old', 'new', 'system', 'auto'],
                       default='auto', help="HarfBuzz engine version to use. "
                       "Default: auto.")
    debug.add_argument('--nowindow', action='store_true', help="Don't show "
                       "the main window.")
    debug.add_argument('--debug-exit', help="Turn on debugging of late exit.",
                       action='store_true')
    debug.add_argument('--no-crash-dialog', action='store_true', help="Don't "
                       "show a crash dialog.")
    # For the Qt args, we use store_const with const=True rather than
    # store_true because we want the default to be None, to make
    # utils.qt:get_args easier.
    debug.add_argument('--qt-style', help="Set the Qt GUI style to use.",
                       metavar='STYLE')
    debug.add_argument('--qt-stylesheet', help="Override the Qt application "
                       "stylesheet.", metavar='STYLESHEET')
    debug.add_argument('--qt-widgetcount', help="Print debug message at the "
                       "end about number of widgets left undestroyed and "
                       "maximum number of widgets existed at the same time.",
                       action='store_const', const=True)
    debug.add_argument('--qt-reverse', help="Set the application's layout "
                       "direction to right-to-left.", action='store_const',
                       const=True)
    debug.add_argument('--qt-qmljsdebugger', help="Activate the QML/JS "
                       "debugger with a specified port. 'block' is optional "
                       "and will make the application wait until a debugger "
                       "connects to it.", metavar='port:PORT[,block]')
    parser.add_argument('command', nargs='*', help="Commands to execute on "
                        "startup.", metavar=':command')
    # URLs will actually be in command
    parser.add_argument('url', nargs='*', help="URLs to open on startup "
                        "(empty as a window separator).")
    return parser


def main():
    """Main entry point for qutebrowser."""
    parser = get_argparser()
    args = parser.parse_args()
    earlyinit.earlyinit(args)
    # We do this imports late as earlyinit needs to be run first (because of
    # the harfbuzz fix and version checking).
    from qutebrowser import app
    import PyQt5.QtWidgets as QtWidgets
    app = app.Application(args)

    def qt_mainloop():
        """Simple wrapper to get a nicer stack trace for segfaults.

        WARNING: misc/crashdialog.py checks the stacktrace for this function
        name, so if this is changed, it should be changed there as well!
        """
        return app.exec_()  # pylint: disable=maybe-no-member

    # We set qApp explicitely here to reduce the risk of segfaults while
    # quitting.
    # See https://bugs.launchpad.net/ubuntu/+source/python-qt4/+bug/561303/comments/7
    # While this is a workaround for PyQt4 which should be fixed in PyQt, it
    # seems this still reduces segfaults.
    # FIXME: We should do another attempt at contacting upstream about this.
    QtWidgets.qApp = app
    ret = qt_mainloop()
    QtWidgets.qApp = None
    return ret
