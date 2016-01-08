# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os.path

import pytest_bdd as bdd

from helpers import utils

bdd.scenarios('urlmarks.feature')


def _check_bookmarks(quteproc, expected, contains):
    """Make sure the given line does (not) exist in the bookmarks.

    Args:
        expected: The line to search for.
        contains: True if the line should be there, False otherwise.
    """
    bookmark_file = os.path.join(quteproc.basedir, 'config', 'bookmarks',
                                 'urls')

    quteproc.clear_data()  # So we don't match old messages
    quteproc.send_cmd(':save')
    quteproc.wait_for(message='Saved to {}'.format(bookmark_file))

    with open(bookmark_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    matched_line = any(
        utils.pattern_match(pattern=expected, value=line.rstrip('\n'))
        for line in lines)

    assert matched_line == contains, lines


@bdd.then(bdd.parsers.parse('the bookmark file should contain "{line}"'))
def bookmark_file_contains(quteproc, line):
    _check_bookmarks(quteproc, line, True)


@bdd.then(bdd.parsers.parse('the bookmark file should not contain "{line}"'))
def bookmark_file_does_not_contain(quteproc, line):
    _check_bookmarks(quteproc, line, False)
