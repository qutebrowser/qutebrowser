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

    'qutebrowser/browser/tabhistory.py',
    'qutebrowser/browser/http.py',
    'qutebrowser/browser/rfc6266.py',
    'qutebrowser/browser/webelem.py',
    'qutebrowser/browser/network/schemehandler.py',
    'qutebrowser/browser/network/filescheme.py',
    'qutebrowser/browser/network/networkreply.py',
    'qutebrowser/browser/signalfilter.py',

    'qutebrowser/misc/readline.py',
    'qutebrowser/misc/split.py',
    'qutebrowser/misc/msgbox.py',

    'qutebrowser/mainwindow/statusbar/keystring.py',
    'qutebrowser/mainwindow/statusbar/percentage.py',
    'qutebrowser/mainwindow/statusbar/progress.py',
    'qutebrowser/mainwindow/statusbar/tabindex.py',
    'qutebrowser/mainwindow/statusbar/textbase.py',

    'qutebrowser/config/configtypes.py',
    'qutebrowser/config/configdata.py',
    'qutebrowser/config/configexc.py',
    'qutebrowser/config/textwrapper.py',

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


def main():
    """Main entry point.

    Return:
        The return code to return.
    """
    utils.change_cwd()

    if sys.platform != 'linux':
        print("Skipping coverage checks on non-Linux system.")
        sys.exit()
    elif '-k' in sys.argv[1:]:
        print("Skipping coverage checks because -k is given.")
        sys.exit()
    elif '-m' in sys.argv[1:]:
        print("Skipping coverage checks because -m is given.")
        sys.exit()
    elif any(arg.startswith('tests' + os.sep) for arg in sys.argv[1:]):
        print("Skipping coverage checks because a filename is given.")
        sys.exit()

    for path in PERFECT_FILES:
        assert os.path.exists(os.path.join(*path.split('/'))), path

    with open('.coverage.xml', encoding='utf-8') as f:
        tree = ElementTree.parse(f)
    classes = tree.getroot().findall('./packages/package/classes/class')

    status = 0

    for klass in classes:
        filename = klass.attrib['filename']
        line_cov = float(klass.attrib['line-rate']) * 100
        branch_cov = float(klass.attrib['branch-rate']) * 100

        assert 0 <= line_cov <= 100, line_cov
        assert 0 <= branch_cov <= 100, branch_cov
        assert '\\' not in filename, filename
        assert '/' in filename, filename

        # Files without any branches have 0% coverage
        if branch_cov < 100 and klass.find('./lines/line[@branch="true"]'):
            is_bad = True
        else:
            is_bad = line_cov < 100

        if filename in PERFECT_FILES and is_bad:
            status = 1
            print("{} has {}% line and {}% branch coverage!".format(
                filename, line_cov, branch_cov))
        elif filename not in PERFECT_FILES and not is_bad:
            status = 1
            print("{} has 100% coverage but is not in PERFECT_FILES!".format(
                filename))

    os.remove('.coverage.xml')

    return status


if __name__ == '__main__':
    sys.exit(main())
