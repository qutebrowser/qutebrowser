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

"""Tests for qutebrowser.utils.readline."""

# pylint: disable=protected-access

import inspect
import unittest
from unittest import mock

from PyQt5.QtWidgets import QLineEdit

from qutebrowser.utils import readline
from qutebrowser.test import stubs


class NoneWidgetTests(unittest.TestCase):

    """Tests when the focused widget is None."""

    def setUp(self):
        readline.QApplication = stubs.FakeQApplication()
        readline.QApplication.focusWidget = mock.Mock(return_value=None)
        self.bridge = readline.ReadlineBridge()

    def test_none(self):
        """Test if there are no exceptions when the widget is None."""
        for name, method in inspect.getmembers(self.bridge, inspect.ismethod):
            with self.subTest(name=name):
                if name.startswith('rl_'):
                    method()


class ReadlineBridgeTest(unittest.TestCase):

    """Tests for readline bridge."""

    def setUp(self):
        self.qle = mock.Mock()
        self.qle.__class__ = QLineEdit
        readline.QApplication.focusWidget = mock.Mock(return_value=self.qle)
        self.bridge = readline.ReadlineBridge()

    def _set_selected_text(self, text):
        """Set the value the fake QLineEdit should return for selectedText."""
        self.qle.configure_mock(**{'selectedText.return_value': text})

    def test_rl_backward_char(self):
        """Test rl_backward_char."""
        self.bridge.rl_backward_char()
        self.qle.cursorBackward.assert_called_with(False)

    def test_rl_forward_char(self):
        """Test rl_forward_char."""
        self.bridge.rl_forward_char()
        self.qle.cursorForward.assert_called_with(False)

    def test_rl_backward_word(self):
        """Test rl_backward_word."""
        self.bridge.rl_backward_word()
        self.qle.cursorWordBackward.assert_called_with(False)

    def test_rl_forward_word(self):
        """Test rl_forward_word."""
        self.bridge.rl_forward_word()
        self.qle.cursorWordForward.assert_called_with(False)

    def test_rl_beginning_of_line(self):
        """Test rl_beginning_of_line."""
        self.bridge.rl_beginning_of_line()
        self.qle.home.assert_called_with(False)

    def test_rl_end_of_line(self):
        """Test rl_end_of_line."""
        self.bridge.rl_end_of_line()
        self.qle.end.assert_called_with(False)

    def test_rl_delete_char(self):
        """Test rl_delete_char."""
        self.bridge.rl_delete_char()
        self.qle.del_.assert_called_with()

    def test_rl_backward_delete_char(self):
        """Test rl_backward_delete_char."""
        self.bridge.rl_backward_delete_char()
        self.qle.backspace.assert_called_with()

    def test_rl_unix_line_discard(self):
        """Set a selected text, delete it, see if it comes back with yank."""
        self._set_selected_text("delete test")
        self.bridge.rl_unix_line_discard()
        self.qle.home.assert_called_with(True)
        self.assertEqual(self.bridge._deleted[self.qle], "delete test")
        self.qle.del_.assert_called_with()
        self.bridge.rl_yank()
        self.qle.insert.assert_called_with("delete test")

    def test_rl_kill_line(self):
        """Set a selected text, delete it, see if it comes back with yank."""
        self._set_selected_text("delete test")
        self.bridge.rl_kill_line()
        self.qle.end.assert_called_with(True)
        self.assertEqual(self.bridge._deleted[self.qle], "delete test")
        self.qle.del_.assert_called_with()
        self.bridge.rl_yank()
        self.qle.insert.assert_called_with("delete test")

    def test_rl_unix_word_rubout(self):
        """Set a selected text, delete it, see if it comes back with yank."""
        self._set_selected_text("delete test")
        self.bridge.rl_unix_word_rubout()
        self.qle.cursorWordBackward.assert_called_with(True)
        self.assertEqual(self.bridge._deleted[self.qle], "delete test")
        self.qle.del_.assert_called_with()
        self.bridge.rl_yank()
        self.qle.insert.assert_called_with("delete test")

    def test_rl_kill_word(self):
        """Set a selected text, delete it, see if it comes back with yank."""
        self._set_selected_text("delete test")
        self.bridge.rl_kill_word()
        self.qle.cursorWordForward.assert_called_with(True)
        self.assertEqual(self.bridge._deleted[self.qle], "delete test")
        self.qle.del_.assert_called_with()
        self.bridge.rl_yank()
        self.qle.insert.assert_called_with("delete test")

    def test_rl_yank_no_text(self):
        """Test yank without having deleted anything."""
        self.bridge.rl_yank()
        self.assertFalse(self.qle.insert.called)


if __name__ == '__main__':
    unittest.main()
