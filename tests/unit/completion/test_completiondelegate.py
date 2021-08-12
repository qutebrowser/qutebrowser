# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.
from unittest import mock

import hypothesis
import hypothesis.strategies
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextDocument, QColor
from PyQt5.QtWidgets import QTextEdit

from qutebrowser.completion import completiondelegate


@pytest.mark.parametrize('pat,txt,segments', [
    ('foo', 'foo', [(0, 3)]),
    ('foo', 'foobar', [(0, 3)]),
    ('foo', 'FOObar', [(0, 3)]),  # re.IGNORECASE
    ('foo', 'barfoo', [(3, 3)]),
    ('foo', 'barfoobaz', [(3, 3)]),
    ('foo', 'barfoobazfoo', [(3, 3), (9, 3)]),
    ('foo', 'foofoo', [(0, 3), (3, 3)]),
    ('a b', 'cadb', [(1, 1), (3, 1)]),
    ('foo', '<foo>', [(1, 3)]),
    ('<a>', "<a>bc", [(0, 3)]),

    # https://github.com/qutebrowser/qutebrowser/issues/4199
    ('foo', "'foo'", [(1, 3)]),
    ('x', "'x'", [(1, 1)]),
    ('lt', "<lt", [(1, 2)]),

    # See https://github.com/qutebrowser/qutebrowser/pull/5111
    ('bar', '\U0001d65b\U0001d664\U0001d664bar', [(6, 3)]),
    ('an anomaly', 'an anomaly', [(0, 2), (3, 7)]),
])
def test_highlight(pat, txt, segments):
    doc = QTextDocument(txt)
    highlighter = completiondelegate._Highlighter(doc, pat, Qt.red)
    highlighter.setFormat = mock.Mock()
    highlighter.highlightBlock(txt)
    highlighter.setFormat.assert_has_calls([
        mock.call(s[0], s[1], mock.ANY) for s in segments
    ])


def test_benchmark_highlight(benchmark):
    txt = 'boofoobar'
    pat = 'foo bar'
    doc = QTextDocument(txt)

    def bench():
        highlighter = completiondelegate._Highlighter(doc, pat, Qt.red)
        highlighter.highlightBlock(txt)

    benchmark(bench)


@hypothesis.given(text=hypothesis.strategies.text())
def test_pattern_hypothesis(text):
    """Make sure we can't produce invalid patterns."""
    doc = QTextDocument()
    completiondelegate._Highlighter(doc, text, Qt.red)


def test_highlighted(qtbot):
    """Make sure highlighting works.

    Note that with Qt > 5.12.1 we need to call setPlainText *after*
    creating the highlighter for highlighting to work. Ideally, we'd test
    whether CompletionItemDelegate._get_textdoc() works properly, but testing
    that is kind of hard, so we just test it in isolation here.
    """
    doc = QTextDocument()
    completiondelegate._Highlighter(doc, 'Hello', Qt.red)
    doc.setPlainText('Hello World')

    # Needed so the highlighting actually works.
    edit = QTextEdit()
    qtbot.add_widget(edit)
    edit.setDocument(doc)

    colors = [f.foreground().color() for f in doc.allFormats()]
    assert QColor('red') in colors
