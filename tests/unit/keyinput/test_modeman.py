# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest

from qutebrowser.keyinput import keyutils
from qutebrowser.misc import objects
from qutebrowser.qt import QtCore
from qutebrowser.utils import usertypes


class FakeKeyparser(QtCore.QObject):

    """A fake BaseKeyParser which doesn't handle anything."""

    keystring_updated = QtCore.pyqtSignal(str)
    request_leave = QtCore.pyqtSignal(usertypes.KeyMode, str, bool)

    def __init__(self):
        super().__init__()
        self.passthrough = False

    def handle(self, evt, *, dry_run=False):
        return False


@pytest.fixture
def modeman(mode_manager):
    mode_manager.register(usertypes.KeyMode.normal, FakeKeyparser())
    return mode_manager


@pytest.fixture(autouse=True)
def set_qapp(monkeypatch, qapp):
    monkeypatch.setattr(objects, 'qapp', qapp)


@pytest.mark.parametrize(
    'key, modifiers, filtered',
    [
        (QtCore.Qt.Key_A, QtCore.Qt.NoModifier, True),
        (QtCore.Qt.Key_Up, QtCore.Qt.NoModifier, False),
        # https://github.com/qutebrowser/qutebrowser/issues/1207
        (QtCore.Qt.Key_A, QtCore.Qt.ShiftModifier, True),
        (QtCore.Qt.Key_A, QtCore.Qt.ShiftModifier | QtCore.Qt.ControlModifier, False),
    ],
)
def test_non_alphanumeric(key, modifiers, filtered, modeman):
    """Make sure non-alphanumeric keys are passed through correctly."""
    evt = keyutils.KeyInfo(key=key, modifiers=modifiers).to_event()
    assert modeman.handle_event(evt) == filtered
