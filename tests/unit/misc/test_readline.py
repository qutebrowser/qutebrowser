# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.misc.readline."""

import re
import inspect

from PyQt5.QtWidgets import QLineEdit, QApplication
import pytest

from qutebrowser.misc import readline


# Some functions aren't 100% readline compatible:
# https://github.com/The-Compiler/qutebrowser/issues/678
# Those are marked with fixme and have another value marked with '# wrong'
# which marks the current behavior.

fixme = pytest.mark.xfail(reason='readline compatibility - see #678')


class LineEdit(QLineEdit):

    """QLineEdit with some methods to make testing easier."""

    def _get_index(self, haystack, needle):
        """Get the index of a char (needle) in a string (haystack).

        Return:
            The position where needle was found, or None if it wasn't found.
        """
        try:
            return haystack.index(needle)
        except ValueError:
            return None

    def set_aug_text(self, text):
        """Set a text with </> markers for selected text and | as cursor."""
        real_text = re.sub('[<>|]', '', text)
        self.setText(real_text)

        cursor_pos = self._get_index(text, '|')
        sel_start_pos = self._get_index(text, '<')
        sel_end_pos = self._get_index(text, '>')

        if sel_start_pos is not None and sel_end_pos is None:
            raise ValueError("< given without >!")
        if sel_start_pos is None and sel_end_pos is not None:
            raise ValueError("> given without <!")

        if cursor_pos is not None:
            if sel_start_pos is not None or sel_end_pos is not None:
                raise ValueError("Can't mix | and </>!")
            self.setCursorPosition(cursor_pos)
        elif sel_start_pos is not None:
            if sel_start_pos > sel_end_pos:
                raise ValueError("< given after >!")
            sel_len = sel_end_pos - sel_start_pos - 1
            self.setSelection(sel_start_pos, sel_len)

    def aug_text(self):
        """Get a text with </> markers for selected text and | as cursor."""
        text = self.text()
        chars = list(text)
        cur_pos = self.cursorPosition()
        assert cur_pos >= 0
        chars.insert(cur_pos, '|')
        if self.hasSelectedText():
            selected_text = self.selectedText()
            sel_start = self.selectionStart()
            sel_end = sel_start + len(selected_text)
            assert sel_start > 0
            assert sel_end > 0
            assert sel_end > sel_start
            assert cur_pos == sel_end
            assert text[sel_start:sel_end] == selected_text
            chars.insert(sel_start, '<')
            chars.insert(sel_end + 1, '>')
        return ''.join(chars)


@pytest.fixture
def lineedit(qtbot, monkeypatch):
    """Fixture providing a LineEdit."""
    le = LineEdit()
    qtbot.add_widget(le)
    monkeypatch.setattr(QApplication.instance(), 'focusWidget', lambda: le)
    return le


@pytest.fixture
def bridge():
    """Fixture providing a ReadlineBridge."""
    return readline.ReadlineBridge()


def test_none(bridge, qtbot):
    """Call each rl_* method with a None focusWidget."""
    assert QApplication.instance().focusWidget() is None
    for name, method in inspect.getmembers(bridge, inspect.ismethod):
        if name.startswith('rl_'):
            method()


@pytest.mark.parametrize('text, expected', [('f<oo>bar', 'fo|obar'),
                                            ('|foobar', '|foobar')])
def test_rl_backward_char(text, expected, lineedit, bridge):
    """Test rl_backward_char."""
    lineedit.set_aug_text(text)
    bridge.rl_backward_char()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, expected', [('f<oo>bar', 'foob|ar'),
                                            ('foobar|', 'foobar|')])
def test_rl_forward_char(text, expected, lineedit, bridge):
    """Test rl_forward_char."""
    lineedit.set_aug_text(text)
    bridge.rl_forward_char()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, expected', [('one <tw>o', 'one |two'),
                                            ('<one >two', '|one two'),
                                            ('|one two', '|one two')])
def test_rl_backward_word(text, expected, lineedit, bridge):
    """Test rl_backward_word."""
    lineedit.set_aug_text(text)
    bridge.rl_backward_word()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, expected', [
    fixme(('<o>ne two', 'one| two')),
    ('<o>ne two', 'one |two'),  # wrong
    fixme(('<one> two', 'one two|')),
    ('<one> two', 'one |two'),  # wrong
    ('one t<wo>', 'one two|')
])
def test_rl_forward_word(text, expected, lineedit, bridge):
    """Test rl_forward_word."""
    lineedit.set_aug_text(text)
    bridge.rl_forward_word()
    assert lineedit.aug_text() == expected


def test_rl_beginning_of_line(lineedit, bridge):
    """Test rl_beginning_of_line."""
    lineedit.set_aug_text('f<oo>bar')
    bridge.rl_beginning_of_line()
    assert lineedit.aug_text() == '|foobar'


def test_rl_end_of_line(lineedit, bridge):
    """Test rl_end_of_line."""
    lineedit.set_aug_text('f<oo>bar')
    bridge.rl_end_of_line()
    assert lineedit.aug_text() == 'foobar|'


@pytest.mark.parametrize('text, expected', [('foo|bar', 'foo|ar'),
                                            ('foobar|', 'foobar|'),
                                            ('|foobar', '|oobar'),
                                            ('f<oo>bar', 'f|bar')])
def test_rl_delete_char(text, expected, lineedit, bridge):
    """Test rl_delete_char."""
    lineedit.set_aug_text(text)
    bridge.rl_delete_char()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, expected', [('foo|bar', 'fo|bar'),
                                            ('foobar|', 'fooba|'),
                                            ('|foobar', '|foobar'),
                                            ('f<oo>bar', 'f|bar')])
def test_rl_backward_delete_char(text, expected, lineedit, bridge):
    """Test rl_backward_delete_char."""
    lineedit.set_aug_text(text)
    bridge.rl_backward_delete_char()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, deleted, rest', [
    ('delete this| test', 'delete this', '| test'),
    fixme(('delete <this> test', 'delete this', '| test')),
    ('delete <this> test', 'delete ', '|this test'),  # wrong
    fixme(('f<oo>bar', 'foo', '|bar')),
    ('f<oo>bar', 'f', '|oobar'),  # wrong
])
def test_rl_unix_line_discard(lineedit, bridge, text, deleted, rest):
    """Delete from the cursor to the beginning of the line and yank back."""
    lineedit.set_aug_text(text)
    bridge.rl_unix_line_discard()
    assert bridge._deleted[lineedit] == deleted
    assert lineedit.aug_text() == rest
    lineedit.clear()
    bridge.rl_yank()
    assert lineedit.aug_text() == deleted + '|'


@pytest.mark.parametrize('text, deleted, rest', [
    ('test |delete this', 'delete this', 'test |'),
    fixme(('<test >delete this', 'test delete this', 'test |')),
    ('<test >delete this', 'test delete this', '|'),  # wrong
])
def test_rl_kill_line(lineedit, bridge, text, deleted, rest):
    """Delete from the cursor to the end of line and yank back."""
    lineedit.set_aug_text(text)
    bridge.rl_kill_line()
    assert bridge._deleted[lineedit] == deleted
    assert lineedit.aug_text() == rest
    lineedit.clear()
    bridge.rl_yank()
    assert lineedit.aug_text() == deleted + '|'


@pytest.mark.parametrize('text, deleted, rest', [
    ('test delete|foobar', 'delete', 'test |foobar'),
    ('test delete |foobar', 'delete ', 'test |foobar'),
    ('open -t github.com/foo/bar  |', 'github.com/foo/bar  ', 'open -t |'),
    ('open -t |github.com/foo/bar', '-t ', 'open |github.com/foo/bar'),
    fixme(('test del<ete>foobar', 'delete', 'test |foobar')),
    ('test del<ete >foobar', 'del', 'test |ete foobar'),  # wrong
])
def test_rl_unix_word_rubout(lineedit, bridge, text, deleted, rest):
    """Delete to word beginning and see if it comes back with yank."""
    lineedit.set_aug_text(text)
    bridge.rl_unix_word_rubout()
    assert bridge._deleted[lineedit] == deleted
    assert lineedit.aug_text() == rest
    lineedit.clear()
    bridge.rl_yank()
    assert lineedit.aug_text() == deleted + '|'


@pytest.mark.parametrize('text, deleted, rest', [
    fixme(('test foobar| delete', ' delete', 'test foobar|')),
    ('test foobar| delete', ' ', 'test foobar|delete'),  # wrong
    fixme(('test foo|delete bar', 'delete', 'test foo| bar')),
    ('test foo|delete bar', 'delete ', 'test foo|bar'),  # wrong
    fixme(('test foo<bar> delete', ' delete', 'test foobar|')),
    ('test foo<bar>delete', 'bardelete', 'test foo|'),  # wrong
])
def test_rl_kill_word(lineedit, bridge, text, deleted, rest):
    """Delete to word end and see if it comes back with yank."""
    lineedit.set_aug_text(text)
    bridge.rl_kill_word()
    assert bridge._deleted[lineedit] == deleted
    assert lineedit.aug_text() == rest
    lineedit.clear()
    bridge.rl_yank()
    assert lineedit.aug_text() == deleted + '|'


def test_rl_yank_no_text(lineedit, bridge):
    """Test yank without having deleted anything."""
    lineedit.clear()
    bridge.rl_yank()
    assert lineedit.aug_text() == '|'
