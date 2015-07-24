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

import sys
import os.path

from lxml import etree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils


PERFECT_FILES = [
    'qutebrowser/commands/cmdexc.py',
    'qutebrowser/config/configtypes.py',
    'qutebrowser/misc/readline.py',

    'qutebrowser/utils/qtutils.py',
    'qutebrowser/utils/standarddir.py',
    'qutebrowser/utils/urlutils.py',
    'qutebrowser/utils/usertypes.py',
    'qutebrowser/utils/utils.py',
    'qutebrowser/utils/version.py',
]


def main():
    """Main entry point.

    Return:
        The return code to return.
    """
    utils.change_cwd()

    for path in PERFECT_FILES:
        assert os.path.exists(os.path.join(*path.split('/'))), path

    with open('coverage.xml', encoding='utf-8') as f:
        tree = etree.parse(f)  # pylint: disable=no-member
    classes = tree.xpath('/coverage/packages/package/classes/class')

    status = 0

    for klass in classes:
        filename = klass.attrib['filename']
        line_cov = float(klass.attrib['line-rate']) * 100
        branch_cov = float(klass.attrib['branch-rate']) * 100

        assert 0 <= line_cov <= 100, line_cov
        assert 0 <= branch_cov <= 100, branch_cov
        assert '\\' not in filename, filename

        if branch_cov < 100 and klass.xpath('lines/line[@branch="true"]'):
            # Files without any branches have 0% coverage
            bad_branch_cov = True
        else:
            bad_branch_cov = False

        if filename in PERFECT_FILES and (line_cov < 100 or bad_branch_cov):
            status = 1
            print("{} has {}% line and {}% branch coverage!".format(
                filename, line_cov, branch_cov))

    return status


if __name__ == '__main__':
    sys.exit(main())
