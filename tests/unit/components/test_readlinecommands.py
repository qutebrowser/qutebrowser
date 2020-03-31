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

import re
import inspect

from PyQt5.QtWidgets import QLineEdit, QApplication
import pytest

from qutebrowser.components import readlinecommands


# Some functions aren't 100% readline compatible:
# https://github.com/qutebrowser/qutebrowser/issues/678
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


def _validate_deletion(lineedit, method, text, deleted, rest):
    """Run and validate a text deletion method on the ReadLine bridge.

    Args:
        lineedit: The LineEdit instance.
        method: Reference to the method on the bridge to test.
        text: The starting 'augmented' text (see LineEdit.set_aug_text)
        deleted: The text that should be deleted when the method is invoked.
        rest: The augmented text that should remain after method is invoked.
    """
    lineedit.set_aug_text(text)
    method()
    assert readlinecommands.bridge._deleted[lineedit] == deleted
    assert lineedit.aug_text() == rest
    lineedit.clear()
    readlinecommands.rl_yank()
    assert lineedit.aug_text() == deleted + '|'


@pytest.fixture
def lineedit(qtbot, monkeypatch):
    """Fixture providing a LineEdit."""
    le = LineEdit()
    qtbot.add_widget(le)
    monkeypatch.setattr(QApplication.instance(), 'focusWidget', lambda: le)
    return le


def test_none(qtbot):
    """Call each rl_* method with a None focusWidget."""
    assert QApplication.instance().focusWidget() is None
    for name, method in inspect.getmembers(readlinecommands,
                                           inspect.isfunction):
        if name.startswith('rl_'):
            method()


@pytest.mark.parametrize('text, expected', [('f<oo>bar', 'fo|obar'),
                                            ('|foobar', '|foobar')])
def test_rl_backward_char(text, expected, lineedit):
    """Test rl_backward_char."""
    lineedit.set_aug_text(text)
    readlinecommands.rl_backward_char()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, expected', [('f<oo>bar', 'foob|ar'),
                                            ('foobar|', 'foobar|')])
def test_rl_forward_char(text, expected, lineedit):
    """Test rl_forward_char."""
    lineedit.set_aug_text(text)
    readlinecommands.rl_forward_char()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, expected', [('one <tw>o', 'one |two'),
                                            ('<one >two', '|one two'),
                                            ('|one two', '|one two')])
def test_rl_backward_word(text, expected, lineedit):
    """Test rl_backward_word."""
    lineedit.set_aug_text(text)
    readlinecommands.rl_backward_word()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, expected', [
    pytest.param('<o>ne two', 'one| two', marks=fixme),
    ('<o>ne two', 'one |two'),  # wrong
    pytest.param('<one> two', 'one two|', marks=fixme),
    ('<one> two', 'one |two'),  # wrong
    ('one t<wo>', 'one two|')
])
def test_rl_forward_word(text, expected, lineedit):
    """Test rl_forward_word."""
    lineedit.set_aug_text(text)
    readlinecommands.rl_forward_word()
    assert lineedit.aug_text() == expected


def test_rl_beginning_of_line(lineedit):
    """Test rl_beginning_of_line."""
    lineedit.set_aug_text('f<oo>bar')
    readlinecommands.rl_beginning_of_line()
    assert lineedit.aug_text() == '|foobar'


def test_rl_end_of_line(lineedit):
    """Test rl_end_of_line."""
    lineedit.set_aug_text('f<oo>bar')
    readlinecommands.rl_end_of_line()
    assert lineedit.aug_text() == 'foobar|'


@pytest.mark.parametrize('text, expected', [('foo|bar', 'foo|ar'),
                                            ('foobar|', 'foobar|'),
                                            ('|foobar', '|oobar'),
                                            ('f<oo>bar', 'f|bar')])
def test_rl_delete_char(text, expected, lineedit):
    """Test rl_delete_char."""
    lineedit.set_aug_text(text)
    readlinecommands.rl_delete_char()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, expected', [('foo|bar', 'fo|bar'),
                                            ('foobar|', 'fooba|'),
                                            ('|foobar', '|foobar'),
                                            ('f<oo>bar', 'f|bar')])
def test_rl_backward_delete_char(text, expected, lineedit):
    """Test rl_backward_delete_char."""
    lineedit.set_aug_text(text)
    readlinecommands.rl_backward_delete_char()
    assert lineedit.aug_text() == expected


@pytest.mark.parametrize('text, deleted, rest', [
    ('delete this| test', 'delete this', '| test'),
    pytest.param('delete <this> test', 'delete this', '| test', marks=fixme),
    ('delete <this> test', 'delete ', '|this test'),  # wrong
    pytest.param('f<oo>bar', 'foo', '|bar', marks=fixme),
    ('f<oo>bar', 'f', '|oobar'),  # wrong
])
def test_rl_unix_line_discard(lineedit, text, deleted, rest):
    """Delete from the cursor to the beginning of the line and yank back."""
    _validate_deletion(lineedit, readlinecommands.rl_unix_line_discard,
                       text, deleted, rest)


@pytest.mark.parametrize('text, deleted, rest', [
    ('test |delete this', 'delete this', 'test |'),
    pytest.param('<test >delete this', 'test delete this', 'test |',
                 marks=fixme),
    ('<test >delete this', 'test delete this', '|'),  # wrong
])
def test_rl_kill_line(lineedit, text, deleted, rest):
    """Delete from the cursor to the end of line and yank back."""
    _validate_deletion(lineedit, readlinecommands.rl_kill_line,
                       text, deleted, rest)


@pytest.mark.parametrize('text, deleted, rest', [
    ('test delete|foobar', 'delete', 'test |foobar'),
    ('test delete |foobar', 'delete ', 'test |foobar'),
    ('open -t github.com/foo/bar  |', 'github.com/foo/bar  ', 'open -t |'),
    ('open -t |github.com/foo/bar', '-t ', 'open |github.com/foo/bar'),
    pytest.param('test del<ete>foobar', 'delete', 'test |foobar',
                 marks=fixme),
    ('test del<ete >foobar', 'del', 'test |ete foobar'),  # wrong
])
def test_rl_unix_word_rubout(lineedit, text, deleted, rest):
    """Delete to word beginning and see if it comes back with yank."""
    _validate_deletion(lineedit, readlinecommands.rl_unix_word_rubout,
                       text, deleted, rest)


@pytest.mark.parametrize('text, deleted, rest', [
    ('test delete|foobar', 'delete', 'test |foobar'),
    ('test delete |foobar', 'delete ', 'test |foobar'),
    ('open -t github.com/foo/bar  |', 'bar  ', 'open -t github.com/foo/|'),
    ('open -t |github.com/foo/bar', '-t ', 'open |github.com/foo/bar'),
    ('open foo/bar.baz|', 'bar.baz', 'open foo/|'),
])
def test_rl_unix_filename_rubout(lineedit, text, deleted, rest):
    """Delete filename segment and see if it comes back with yank."""
    _validate_deletion(lineedit, readlinecommands.rl_unix_filename_rubout,
                       text, deleted, rest)


@pytest.mark.parametrize('text, deleted, rest', [
    pytest.param('test foobar| delete', ' delete', 'test foobar|',
                 marks=fixme),
    ('test foobar| delete', ' ', 'test foobar|delete'),  # wrong
    pytest.param('test foo|delete bar', 'delete', 'test foo| bar',
                 marks=fixme),
    ('test foo|delete bar', 'delete ', 'test foo|bar'),  # wrong
    pytest.param('test foo<bar> delete', ' delete', 'test foobar|',
                 marks=fixme),
    ('test foo<bar>delete', 'bardelete', 'test foo|'),  # wrong
])
def test_rl_kill_word(lineedit, text, deleted, rest):
    """Delete to word end and see if it comes back with yank."""
    _validate_deletion(lineedit, readlinecommands.rl_kill_word,
                       text, deleted, rest)


@pytest.mark.parametrize('text, deleted, rest', [
    ('test delete|foobar', 'delete', 'test |foobar'),
    ('test delete |foobar', 'delete ', 'test |foobar'),
    ('open -t github.com/foo/bar  |', 'bar  ', 'open -t github.com/foo/|'),
    ('open -t |github.com/foo/bar', 't ', 'open -|github.com/foo/bar'),
    pytest.param('test del<ete>foobar', 'delete', 'test |foobar', marks=fixme),
    ('test del<ete >foobar', 'del', 'test |ete foobar'),  # wrong
    ('open foo/bar.baz|', 'baz', 'open foo/bar.|'),
])
def test_rl_backward_kill_word(lineedit, text, deleted, rest):
    """Delete to word beginning and see if it comes back with yank."""
    _validate_deletion(lineedit, readlinecommands.rl_backward_kill_word,
                       text, deleted, rest)


def test_rl_yank_no_text(lineedit):
    """Test yank without having deleted anything."""
    lineedit.clear()
    readlinecommands.rl_yank()
    assert lineedit.aug_text() == '|'
