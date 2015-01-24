# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.misc.crashdialog."""

import unittest

from qutebrowser.misc import crashdialog


VALID_CRASH_TEXT = """
Fatal Python error: Segmentation fault
_
Current thread 0x00007f09b538d700 (most recent call first):
  File "", line 1 in testfunc
  File "filename", line 88 in func
"""

VALID_CRASH_TEXT_EMPTY = """
Fatal Python error: Aborted
_
Current thread 0x00007f09b538d700 (most recent call first):
  File "", line 1 in_
  File "filename", line 88 in func
"""

INVALID_CRASH_TEXT = """
Hello world!
"""


class ParseFatalStacktraceTests(unittest.TestCase):

    """Tests for parse_fatal_stacktrace."""

    def test_valid_text(self):
        """Test parse_fatal_stacktrace with a valid text."""
        text = VALID_CRASH_TEXT.strip().replace('_', ' ')
        typ, func = crashdialog.parse_fatal_stacktrace(text)
        self.assertEqual(typ, "Segmentation fault")
        self.assertEqual(func, 'testfunc')

    def test_valid_text(self):
        """Test parse_fatal_stacktrace with a valid text but empty function."""
        text = VALID_CRASH_TEXT_EMPTY.strip().replace('_', ' ')
        typ, func = crashdialog.parse_fatal_stacktrace(text)
        self.assertEqual(typ, 'Aborted')
        self.assertEqual(func, '')

    def test_invalid_text(self):
        """Test parse_fatal_stacktrace with an invalid text."""
        text = INVALID_CRASH_TEXT.strip().replace('_', ' ')
        typ, func = crashdialog.parse_fatal_stacktrace(text)
        self.assertEqual(typ, '')
        self.assertEqual(func, '')


if __name__ == '__main__':
    unittest.main()
