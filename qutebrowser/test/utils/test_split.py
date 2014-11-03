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


class SplitTests(unittest.TestCase):

    """Test split."""

    def test_normal(self):
        """Test split with a simple string."""
        items = split.split('one two')
        self.assertEqual(items, ['one', 'two'])

    def test_quoted(self):
        """Test split with a normally quoted string."""
        items = split.split('one "two three" four')
        self.assertEqual(items, ['one', 'two three', 'four'])

    def test_single_quoted(self):
        """Test split with a single quoted string."""
        items = split.split("one 'two three' four")
        self.assertEqual(items, ['one', 'two three', 'four'])

    def test_escaped(self):
        """Test split with a normal escaped string."""
        items = split.split(r'one "two\" three" four')
        self.assertEqual(items, ['one', 'two" three', 'four'])

    def test_escaped_single(self):
        """Test split with a single escaped string."""
        items = split.split(r"one 'two'\'' three' four")
        self.assertEqual(items, ['one', "two' three", 'four'])

    def test_unbalanced_quotes(self):
        """Test split with unbalanded quotes."""
        items = split.split(r'one "two three')
        self.assertEqual(items, ['one', 'two three'])

    def test_unbalanced_single_quotes(self):
        """Test split with unbalanded single quotes."""
        items = split.split(r"one 'two three")
        self.assertEqual(items, ['one', "two three"])

    def test_unfinished_escape(self):
        """Test split with an unfinished escape."""
        items = split.split('one\\')
        self.assertEqual(items, ['one\\'])

    def test_both(self):
        """Test split with an unfinished escape and quotes.."""
        items = split.split('one "two\\')
        self.assertEqual(items, ['one', 'two\\'])
