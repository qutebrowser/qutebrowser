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

"""Tests for qutebrowser.utils.split."""

import unittest

from qutebrowser.utils import split


test_data = r"""
one two|one|two|
one "two three" four|one|two three|four|
one 'two three' four|one|two three|four|
one "two\" three" four|one|two" three|four|
one 'two'\'' three' four|one|two' three|four|
one "two three|one|two three|
one 'two three|one|two three|
one\|one\|
one "two\|one|two\|
"""

class SplitTests(unittest.TestCase):

    """Test split."""

    def test_split(self):
        """Test splitting."""
        for case in test_data.strip().splitlines():
            cmd, *out = case.split('|')[:-1]
            cmd = cmd.replace(r'\n', '\n')
            with self.subTest(cmd=cmd):
                items = split.split(cmd)
                self.assertEqual(items, out)
