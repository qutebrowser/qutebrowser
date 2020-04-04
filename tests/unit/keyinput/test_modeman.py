# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest

from PyQt5.QtCore import Qt, QObject, pyqtSignal

from qutebrowser.utils import usertypes


class FakeKeyparser(QObject):

    """A fake BaseKeyParser which doesn't handle anything."""

    request_leave = pyqtSignal(usertypes.KeyMode, str, bool)

    def __init__(self):
        super().__init__()
        self.passthrough = False

    def handle(self, evt, *, dry_run=False):
        return False


@pytest.fixture
def modeman(mode_manager):
    mode_manager.register(usertypes.KeyMode.normal, FakeKeyparser())
    return mode_manager


@pytest.mark.parametrize('key, modifiers, filtered', [
    (Qt.Key_A, Qt.NoModifier, True),
    (Qt.Key_Up, Qt.NoModifier, False),
    # https://github.com/qutebrowser/qutebrowser/issues/1207
    (Qt.Key_A, Qt.ShiftModifier, True),
    (Qt.Key_A, Qt.ShiftModifier | Qt.ControlModifier, False),
])
def test_non_alphanumeric(key, modifiers, filtered, fake_keyevent, modeman):
    """Make sure non-alphanumeric keys are passed through correctly."""
    evt = fake_keyevent(key=key, modifiers=modifiers)
    assert modeman.handle_event(evt) == filtered
