#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Enforce perfect coverage on some files."""

import os
import sys
import os.path

from xml.etree import ElementTree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils


PERFECT_FILES = [
    'qutebrowser/commands/cmdexc.py',
    'qutebrowser/commands/cmdutils.py',
    'qutebrowser/commands/argparser.py',

    'qutebrowser/browser/cookies.py',
    'qutebrowser/browser/tabhistory.py',
    'qutebrowser/browser/http.py',
    'qutebrowser/browser/rfc6266.py',
    'qutebrowser/browser/webelem.py',
    'qutebrowser/browser/network/schemehandler.py',
    'qutebrowser/browser/network/filescheme.py',
    'qutebrowser/browser/network/networkreply.py',
    'qutebrowser/browser/signalfilter.py',

    'qutebrowser/keyinput/basekeyparser.py',

    'qutebrowser/misc/autoupdate.py',
    'qutebrowser/misc/readline.py',
    'qutebrowser/misc/split.py',
    'qutebrowser/misc/msgbox.py',
    'qutebrowser/misc/checkpyver.py',
    'qutebrowser/misc/guiprocess.py',
    'qutebrowser/misc/editor.py',
    'qutebrowser/misc/cmdhistory.py',
    'qutebrowser/misc/ipc.py',

    'qutebrowser/mainwindow/statusbar/keystring.py',
    'qutebrowser/mainwindow/statusbar/percentage.py',
    'qutebrowser/mainwindow/statusbar/progress.py',
    'qutebrowser/mainwindow/statusbar/tabindex.py',
    'qutebrowser/mainwindow/statusbar/textbase.py',

    'qutebrowser/config/configtypes.py',
    'qutebrowser/config/configdata.py',
    'qutebrowser/config/configexc.py',
    'qutebrowser/config/textwrapper.py',
    'qutebrowser/config/style.py',

    'qutebrowser/utils/qtutils.py',
    'qutebrowser/utils/standarddir.py',
    'qutebrowser/utils/urlutils.py',
    'qutebrowser/utils/usertypes.py',
    'qutebrowser/utils/utils.py',
    'qutebrowser/utils/version.py',
    'qutebrowser/utils/debug.py',
    'qutebrowser/utils/jinja.py',
    'qutebrowser/utils/error.py',
]


class Skipped(Exception):

    """Exception raised when skipping coverage checks."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__("Skipping coverage checks " + reason)


def check(fileobj, perfect_files):
    """Main entry point which parses/checks coverage.xml if applicable."""
    if sys.platform != 'linux':
        raise Skipped("on non-Linux system.")
    elif '-k' in sys.argv[1:]:
        raise Skipped("because -k is given.")
    elif '-m' in sys.argv[1:]:
        raise Skipped("because -m is given.")
    elif any(arg.startswith('tests' + os.sep) for arg in sys.argv[1:]):
        raise Skipped("because a filename is given.")

    for path in perfect_files:
        assert os.path.exists(path)

    tree = ElementTree.parse(fileobj)
    classes = tree.getroot().findall('./packages/package/classes/class')

    messages = []

    for klass in classes:
        filename = klass.attrib['filename']
        line_cov = float(klass.attrib['line-rate']) * 100
        branch_cov = float(klass.attrib['branch-rate']) * 100

        assert 0 <= line_cov <= 100, line_cov
        assert 0 <= branch_cov <= 100, branch_cov
        assert '\\' not in filename, filename

        is_bad = line_cov < 100 or branch_cov < 100

        if filename in perfect_files and is_bad:
            messages.append(("{} has {}% line and {}% branch coverage!".format(
                filename, line_cov, branch_cov)))
        elif filename not in perfect_files and not is_bad:
            messages.append("{} has 100% coverage but is not in "
                            "perfect_files!".format(filename))

    return messages


def main():
    """Main entry point.

    Return:
        The return code to return.
    """
    utils.change_cwd()

    try:
        with open('coverage.xml', encoding='utf-8') as f:
            messages = check(f, PERFECT_FILES)
    except Skipped as e:
        print(e)
        messages = []

    for msg in messages:
        print(msg)

    os.remove('coverage.xml')
    return 1 if messages else 0


if __name__ == '__main__':
    sys.exit(main())
