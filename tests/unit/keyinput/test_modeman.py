# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qutebrowser.qt.core import Qt, QObject, pyqtSignal
from qutebrowser.qt.gui import QKeyEvent, QKeySequence

from qutebrowser.utils import usertypes
from qutebrowser.keyinput import keyutils
from qutebrowser.misc import objects


class FakeKeyparser(QObject):

    """A fake BaseKeyParser which doesn't handle anything."""

    keystring_updated = pyqtSignal(str)
    request_leave = pyqtSignal(usertypes.KeyMode, str, bool)

    def __init__(self):
        super().__init__()
        self.passthrough = False

    def handle(
        self,
        evt: QKeyEvent,
        *,
        dry_run: bool = False,
    ) -> QKeySequence.SequenceMatch:
        return QKeySequence.SequenceMatch.NoMatch


@pytest.fixture
def modeman(mode_manager):
    mode_manager.register(usertypes.KeyMode.normal, FakeKeyparser())
    return mode_manager


@pytest.fixture(autouse=True)
def set_qapp(monkeypatch, qapp):
    monkeypatch.setattr(objects, 'qapp', qapp)


@pytest.mark.parametrize('key, modifiers, filtered', [
    (Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, True),
    (Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier, False),
    # https://github.com/qutebrowser/qutebrowser/issues/1207
    (Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier, True),
    (Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier, False),
])
def test_non_alphanumeric(key, modifiers, filtered, modeman):
    """Make sure non-alphanumeric keys are passed through correctly."""
    evt = keyutils.KeyInfo(key=key, modifiers=modifiers).to_event()
    assert modeman.handle_event(evt) == filtered
