# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test TextBase widget."""
from qutebrowser.qt.core import Qt
import pytest

from qutebrowser.mainwindow.statusbar.textbase import TextBase


@pytest.mark.parametrize('elidemode, check', [
    (Qt.TextElideMode.ElideRight, lambda s: s.endswith('…') or s.endswith('...')),
    (Qt.TextElideMode.ElideLeft, lambda s: s.startswith('…') or s.startswith('...')),
    (Qt.TextElideMode.ElideMiddle, lambda s: '…' in s or '...' in s),
    (Qt.TextElideMode.ElideNone, lambda s: '…' not in s and '...' not in s),
])
def test_elided_text(fake_statusbar, qtbot, elidemode, check):
    """Ensure that a widget too small to hold the entire label text will elide.

    It is difficult to check what is actually being drawn in a portable way, so
    at least we ensure our customized methods are being called and the elided
    string contains the horizontal ellipsis character.

    Args:
        qtbot: pytestqt.plugin.QtBot fixture
        elidemode: parametrized elide mode
        check: function that receives the elided text and must return True
        if the ellipsis is placed correctly according to elidemode.
    """
    fake_statusbar.container.expose()

    label = TextBase(elidemode=elidemode)
    qtbot.add_widget(label)
    fake_statusbar.hbox.addWidget(label)

    long_string = 'Hello world! ' * 100
    label.setText(long_string)
    label.show()

    assert check(label._elided_text)


def test_resize(qtbot):
    """Make sure the elided text is updated when resizing."""
    label = TextBase()
    qtbot.add_widget(label)
    long_string = 'Hello world! ' * 20
    label.setText(long_string)

    with qtbot.wait_exposed(label):
        label.show()

    text_1 = label._elided_text
    label.resize(20, 50)
    text_2 = label._elided_text

    assert text_1 != text_2


def test_text_elide_none(mocker, qtbot):
    """Make sure the text doesn't get elided if it's empty."""
    label = TextBase()
    qtbot.add_widget(label)
    label.setText('')
    mock = mocker.patch(
        'qutebrowser.mainwindow.statusbar.textbase.TextBase.fontMetrics')
    label._update_elided_text(20)

    assert not mock.called


def test_unset_text(qtbot):
    """Make sure the text is cleared properly."""
    label = TextBase()
    qtbot.add_widget(label)
    label.setText('foo')
    label.setText('')
    assert not label._elided_text
