# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test widgets in miscwidgets module."""

from unittest import mock
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication, QWidget
import pytest

from qutebrowser.misc import miscwidgets


class TestCommandLineEdit:

    """Tests for CommandLineEdit widget."""

    @pytest.fixture
    def cmd_edit(self, qtbot):
        """Fixture to initialize a CommandLineEdit."""
        cmd_edit = miscwidgets.CommandLineEdit()
        cmd_edit.set_prompt(':')
        qtbot.add_widget(cmd_edit)
        assert cmd_edit.text() == ''
        yield cmd_edit

    @pytest.fixture
    def mock_clipboard(self, mocker):
        """Fixture to mock QApplication.clipboard.

        Return:
            The mocked QClipboard object.
        """
        mocker.patch.object(QApplication, 'clipboard')
        clipboard = mock.MagicMock()
        clipboard.supportsSelection.return_value = True
        QApplication.clipboard.return_value = clipboard
        return clipboard

    def test_position(self, qtbot, cmd_edit):
        """Test cursor position based on the prompt."""
        qtbot.keyClicks(cmd_edit, ':hello')
        assert cmd_edit.text() == ':hello'
        assert cmd_edit.cursorPosition() == len(':hello')

        cmd_edit.home(True)
        assert cmd_edit.cursorPosition() == len(':')
        qtbot.keyClick(cmd_edit, Qt.Key_Delete)
        assert cmd_edit.text() == ':'
        qtbot.keyClick(cmd_edit, Qt.Key_Backspace)
        assert cmd_edit.text() == ':'

        qtbot.keyClicks(cmd_edit, 'hey again')
        assert cmd_edit.text() == ':hey again'

    def test_invalid_prompt(self, qtbot, cmd_edit):
        """Test preventing of an invalid prompt being entered."""
        qtbot.keyClicks(cmd_edit, '$hello')
        assert cmd_edit.text() == ''

    def test_selection_home(self, qtbot, cmd_edit):
        """Test selection persisting when pressing home."""
        qtbot.keyClicks(cmd_edit, ':hello')
        assert cmd_edit.text() == ':hello'
        assert cmd_edit.cursorPosition() == len(':hello')
        cmd_edit.home(True)
        assert cmd_edit.cursorPosition() == len(':')
        assert cmd_edit.selectionStart() == len(':')

    def test_selection_cursor_left(self, qtbot, cmd_edit):
        """Test selection persisting when moving to the first char."""
        qtbot.keyClicks(cmd_edit, ':hello')
        assert cmd_edit.text() == ':hello'
        assert cmd_edit.cursorPosition() == len(':hello')
        for _ in ':hello':
            qtbot.keyClick(cmd_edit, Qt.Key_Left, modifier=Qt.ShiftModifier)
        assert cmd_edit.cursorPosition() == len(':')
        assert cmd_edit.selectionStart() == len(':')


class WrappedWidget(QWidget):

    def sizeHint(self):
        return QSize(23, 42)


class TestWrapperLayout:

    @pytest.fixture
    def container(self, qtbot):
        wrapped = WrappedWidget()
        parent = QWidget()
        qtbot.add_widget(wrapped)
        qtbot.add_widget(parent)
        layout = miscwidgets.WrapperLayout(parent)
        layout.wrap(parent, wrapped)
        parent.wrapped = wrapped
        return parent

    def test_size_hint(self, container):
        assert container.sizeHint() == QSize(23, 42)

    def test_wrapped(self, container):
        assert container.wrapped.parent() is container
        assert container.focusProxy() is container.wrapped


class TestFullscreenNotification:

    @pytest.mark.parametrize('bindings, text', [
        ({'<escape>': 'fullscreen --leave'},
         "Press <Escape> to exit fullscreen."),
        ({'<escape>': 'fullscreen'}, "Page is now fullscreen."),
        ({'a': 'fullscreen --leave'}, "Press a to exit fullscreen."),
        ({}, "Page is now fullscreen."),
    ])
    def test_text(self, qtbot, config_stub, key_config_stub, bindings, text):
        config_stub.val.bindings.default = {}
        config_stub.val.bindings.commands = {'normal': bindings}
        w = miscwidgets.FullscreenNotification()
        qtbot.add_widget(w)
        assert w.text() == text

    def test_timeout(self, qtbot, key_config_stub):
        w = miscwidgets.FullscreenNotification()
        qtbot.add_widget(w)
        with qtbot.waitSignal(w.destroyed):
            w.set_timeout(1)
