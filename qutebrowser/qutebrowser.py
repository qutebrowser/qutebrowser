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

"""Early initialization and main entry pint."""


from argparse import ArgumentParser

from qutebrowser.utils.checkpyver import check_python_version
check_python_version()
import qutebrowser.utils.earlyinit as earlyinit


def _parse_args():
    """Parse command line options.

    Return:
        Argument namespace from argparse.
    """
    parser = ArgumentParser("usage: %(prog)s [options]")
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
    debug.add_argument('--debug', help="Turn on debugging options.",
                       action='store_true')
    debug.add_argument('--nocolor', help="Turn off colored logging.",
                       action='store_false', dest='color')
    debug.add_argument('--harfbuzz', choices=['old', 'new', 'system', 'auto'],
                       default='auto', help="HarfBuzz engine version to use. "
                       "Default: auto.")
    # Some notes on the Qt options:
    #  - If a new option is added, it also needs to be added to _get_qt_args in
    #    app.py.
    #  - We use store_const with const=True rather than store_true because we
    #    want the default to be None.
    debug.add_argument('--qt-style', help="Set the Qt GUI style to use.",
                       metavar='STYLE')
    debug.add_argument('--qt-stylesheet', help="Override the Qt application "
                       "stylesheet.", metavar='STYLESHEET')
    debug.add_argument('--qt-widget-count', help="Print debug message at the "
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
    parser.add_argument('url', nargs='*', help="URLs to open on startup.")
    return parser.parse_args()


def main():
    """Main entry point for qutebrowser."""
    earlyinit.init_faulthandler()
    args = _parse_args()
    earlyinit.check_pyqt_core()
    # We do this import late as we need to do the version checking first.
    # Note we may not import webkit stuff yet as fix_harfbuzz didn't run.
    import qutebrowser.utils.log as log
    log.init_log(args)
    earlyinit.fix_harfbuzz(args)
    earlyinit.check_qt_version()
    earlyinit.check_pyqt_webkit()
    earlyinit.check_pkg_resources()
    # We do this import late as we need to fix harfbuzz first.
    from qutebrowser.app import Application
    app = Application(args)
    return app.exec_()
