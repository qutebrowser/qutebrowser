# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.utils.debug."""

import re
import time
import unittest
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyle, QFrame

from qutebrowser.utils import debug
from qutebrowser.test import stubs


class TestDebug(unittest.TestCase):

    """Test signal debug output functions."""

    def setUp(self):
        self.signal = stubs.FakeSignal()

    def test_dbg_signal_newline(self):
        """Test dbg_signal() with a newline."""
        self.assertEqual(debug.dbg_signal(self.signal, ['foo\nbar']),
                         r"fake('foo\nbar')")


if __name__ == '__main__':
    unittest.main()
