# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os.path

import pytest
import pytest_bdd as bdd

from helpers import testutils

bdd.scenarios('urlmarks.feature')


@pytest.fixture(autouse=True)
def clear_marks(quteproc):
    """Clear all existing marks between tests."""
    yield
    quteproc.send_cmd(':quickmark-del --all')
    quteproc.wait_for(message="Quickmarks cleared.")
    quteproc.send_cmd(':bookmark-del --all')
    quteproc.wait_for(message="Bookmarks cleared.")


def _check_marks(quteproc, quickmarks, expected, contains):
    """Make sure the given line does (not) exist in the bookmarks.

    Args:
        quickmarks: True to check the quickmarks file instead of bookmarks.
        expected: The line to search for.
        contains: True if the line should be there, False otherwise.
    """
    if quickmarks:
        mark_file = os.path.join(quteproc.basedir, 'config', 'quickmarks')
    else:
        mark_file = os.path.join(quteproc.basedir, 'config', 'bookmarks',
                                 'urls')

    quteproc.clear_data()  # So we don't match old messages
    quteproc.send_cmd(':save')
    quteproc.wait_for(message='Saved to {}'.format(mark_file))

    with open(mark_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    matched_line = any(
        testutils.pattern_match(pattern=expected, value=line.rstrip('\n'))
        for line in lines)

    assert matched_line == contains, lines


@bdd.then(bdd.parsers.parse('the bookmark file should contain "{line}"'))
def bookmark_file_contains(quteproc, line):
    _check_marks(quteproc, quickmarks=False, expected=line, contains=True)


@bdd.then(bdd.parsers.parse('the bookmark file should not contain "{line}"'))
def bookmark_file_does_not_contain(quteproc, line):
    _check_marks(quteproc, quickmarks=False, expected=line, contains=False)


@bdd.then(bdd.parsers.parse('the quickmark file should contain "{line}"'))
def quickmark_file_contains(quteproc, line):
    _check_marks(quteproc, quickmarks=True, expected=line, contains=True)


@bdd.then(bdd.parsers.parse('the quickmark file should not contain "{line}"'))
def quickmark_file_does_not_contain(quteproc, line):
    _check_marks(quteproc, quickmarks=True, expected=line, contains=False)
