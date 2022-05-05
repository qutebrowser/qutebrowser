# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qutebrowser.qt.core import Qt, QObject, pyqtSignal, QTimer
from qutebrowser.qt.gui import QKeyEvent, QKeySequence

from qutebrowser.utils import usertypes
from qutebrowser.keyinput import keyutils
from qutebrowser.misc import objects


class FakeKeyparser(QObject):

    """A fake BaseKeyParser which doesn't handle anything."""

    keystring_updated = pyqtSignal(str)
    request_leave = pyqtSignal(usertypes.KeyMode, str, bool)
    forward_partial_key = pyqtSignal(str)
    clear_partial_keys = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.passthrough = False
        self.allow_partial_timeout = False
        self.allow_forward = True
        self.forward_widget_name = None

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


class FakeKeyparserWithTimeout(QObject):

    """A minimal fake BaseKeyParser for testing partial timeouts."""

    keystring_updated = pyqtSignal(str)
    request_leave = pyqtSignal(usertypes.KeyMode, str, bool)
    forward_partial_key = pyqtSignal(str)
    clear_partial_keys = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.passthrough = False
        self.allow_partial_timeout = True
        self.allow_forward = True
        self.forward_widget_name = None
        self.fake_clear_keystring_called = False

    def handle(self, evt, *, dry_run=False):
        txt = str(keyutils.KeyInfo.from_event(evt))
        if 'a' == txt:
            return QKeySequence.SequenceMatch.ExactMatch
        elif 'b' == txt:
            return QKeySequence.SequenceMatch.PartialMatch
        else:
            return QKeySequence.SequenceMatch.NoMatch

    def clear_keystring(self):
        self.fake_clear_keystring_called = True
        self.keystring_updated.emit('')


@pytest.fixture
def modeman_with_timeout(mode_manager):
    mode_manager.register(usertypes.KeyMode.normal, FakeKeyparserWithTimeout())
    return mode_manager


@pytest.mark.parametrize('data_sequence', [
    ((Qt.Key.Key_A, 'timer_inactive'),),
    ((Qt.Key.Key_B, 'timer_active'),),
    ((Qt.Key.Key_C, 'timer_inactive'),),
    ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_A, 'timer_inactive'),),
    ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_B, 'timer_reset'),),
    ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_C, 'timer_inactive'),),
    ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_B, 'timer_reset'), (Qt.Key.Key_A, 'timer_inactive'),),
    ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_B, 'timer_reset'), (Qt.Key.Key_B, 'timer_reset'),),
    ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_B, 'timer_reset'), (Qt.Key.Key_C, 'timer_inactive'),),
])
def test_partial_keychain_timeout(modeman_with_timeout, config_stub, qtbot, data_sequence):
    """Test partial keychain timeout behavior."""
    mode = modeman_with_timeout.mode
    timeout = 100
    config_stub.val.input.partial_timeout = timeout
    timer = modeman_with_timeout._partial_timer
    parser = modeman_with_timeout.parsers[mode]
    assert not timer.isActive()

    for key, behavior in data_sequence:
        keyinfo = keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)
        if behavior == 'timer_active':
            # Timer should be active
            modeman_with_timeout.handle_event(keyinfo.to_event())
            assert timer.isSingleShot()
            assert timer.interval() == timeout
            assert timer.isActive()
        elif behavior == 'timer_inactive':
            # Timer should be inactive
            modeman_with_timeout.handle_event(keyinfo.to_event())
            assert not timer.isActive()
            assert not parser.fake_clear_keystring_called
        elif behavior == 'timer_reset':
            # Timer should be reset after handling the key
            half_timer = QTimer()
            half_timer.setSingleShot(True)
            half_timer.setInterval(timeout//2)
            half_timer.start()
            # Simulate a half timeout to check for reset
            qtbot.wait_signal(half_timer.timeout).wait()
            assert (timeout - (timeout//4)) > timer.remainingTime()
            modeman_with_timeout.handle_event(keyinfo.to_event())
            assert (timeout - (timeout//4)) < timer.remainingTime()
            assert timer.isActive()
        else:
            # Unreachable
            assert False
    if behavior in ['timer_active', 'timer_reset']:
        # Now simulate a timeout and check the keystring has been cleared.
        with qtbot.wait_signal(modeman_with_timeout.keystring_updated) as blocker:
            timer.timeout.emit()
        assert parser.fake_clear_keystring_called
        parser.fake_clear_keystring_called = False
        assert blocker.args == [mode, '']

