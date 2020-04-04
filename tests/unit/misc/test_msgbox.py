# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.misc.msgbox."""

import pytest

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QWidget

from qutebrowser.misc import msgbox
from qutebrowser.utils import utils


@pytest.fixture(autouse=True)
def patch_args(fake_args):
    fake_args.no_err_windows = False


def test_attributes(qtbot):
    """Test basic QMessageBox attributes."""
    title = 'title'
    text = 'text'
    parent = QWidget()
    qtbot.add_widget(parent)
    icon = QMessageBox.Critical
    buttons = QMessageBox.Ok | QMessageBox.Cancel

    box = msgbox.msgbox(parent=parent, title=title, text=text, icon=icon,
                        buttons=buttons)
    qtbot.add_widget(box)
    if not utils.is_mac:
        assert box.windowTitle() == title
    assert box.icon() == icon
    assert box.standardButtons() == buttons
    assert box.text() == text
    assert box.parent() is parent


@pytest.mark.parametrize('plain_text, expected', [
    (True, Qt.PlainText),
    (False, Qt.RichText),
    (None, Qt.AutoText),
])
def test_plain_text(qtbot, plain_text, expected):
    box = msgbox.msgbox(parent=None, title='foo', text='foo',
                        icon=QMessageBox.Information, plain_text=plain_text)
    qtbot.add_widget(box)
    assert box.textFormat() == expected


def test_finished_signal(qtbot):
    """Make sure we can pass a slot to be called when the dialog finished."""
    signal_triggered = False

    def on_finished():
        nonlocal signal_triggered
        signal_triggered = True

    box = msgbox.msgbox(parent=None, title='foo', text='foo',
                        icon=QMessageBox.Information, on_finished=on_finished)

    qtbot.add_widget(box)

    with qtbot.waitSignal(box.finished):
        box.accept()

    assert signal_triggered


def test_information(qtbot):
    box = msgbox.information(parent=None, title='foo', text='bar')
    qtbot.add_widget(box)
    if not utils.is_mac:
        assert box.windowTitle() == 'foo'
    assert box.text() == 'bar'
    assert box.icon() == QMessageBox.Information


def test_no_err_windows(fake_args, capsys):
    fake_args.no_err_windows = True
    box = msgbox.information(parent=None, title='foo', text='bar')
    box.exec_()  # should do nothing
    out, err = capsys.readouterr()
    assert not out
    assert err == 'Message box: foo; bar\n'
