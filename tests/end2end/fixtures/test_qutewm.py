# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Daniel Schadt
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

"""Tests for qutewm and the qutewm fixtures."""

from PyQt5.QtWidgets import QMainWindow

import pytest

from qutebrowser.utils import qtutils
from end2end.fixtures import qutewm


@pytest.mark.qutewm
class TestQuteWM:

    # qtbot.wait is used to wait for WAIT_DELAY ms. This makes sure that Qt
    # processed all events (like the focus changed event from the X server),
    # so that QMainWindow.isActiveWindow works as expected and returns the
    # correct result. Waiting for qutewm.window_focused is not enough, as that
    # may fire when Qt hasn't yet registered the change, so we need to give it
    # some time and at least enter the event loop once.
    WAIT_DELAY = 200

    @classmethod
    def get_window(cls):
        """Return a window suitable for testing."""
        window = QMainWindow()
        return window

    def test_single_window(self, qutewm, qtbot, qapp):
        window = self.get_window()
        qtbot.addWidget(window)
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused]):
            window.show()
        qtbot.wait(self.WAIT_DELAY)
        assert window.isActiveWindow()
        with qtbot.waitSignal(qutewm.window_closed):
            window.close()

    def test_qutewm_exits_when_wm_running(self, qtbot):
        new_process = qutewm.QuteWMProcess()
        new_process.start()
        new_process.terminate()
        assert new_process.wm_failed

    def test_focus_on_window_open_and_close(self, qutewm, qtbot):
        window_a = self.get_window()
        window_b = self.get_window()
        qtbot.addWidget(window_a)
        qtbot.addWidget(window_b)

        # Show the first window, it should then have focus
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused]):
            window_a.show()
        qtbot.wait(self.WAIT_DELAY)
        assert window_a.isActiveWindow()

        # Show the second window, it should then have focus
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused]):
            window_b.show()
        qtbot.wait(self.WAIT_DELAY)
        assert window_b.isActiveWindow()

        # Close the second window, focus should revert to the first one
        with qtbot.waitSignals([qutewm.window_closed, qutewm.window_focused]):
            window_b.close()
        qtbot.wait(self.WAIT_DELAY)
        assert window_a.isActiveWindow()

    @pytest.mark.skipif(
        not qtutils.version_check('5.4.0'),
        reason='Urgency hints only work correctly with Qt 5.4')
    def test_focus_on_urgency_hint(self, qutewm, qtbot, qapp):
        window_a = self.get_window()
        window_b = self.get_window()
        qtbot.addWidget(window_a)
        qtbot.addWidget(window_b)

        # Show the first window, it should then have focus
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused]):
            window_a.show()
        qtbot.wait(self.WAIT_DELAY)
        assert window_a.isActiveWindow()

        # Show the second window, it should then have focus
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused]):
            window_b.show()
        qtbot.wait(self.WAIT_DELAY)
        assert window_b.isActiveWindow()

        # Urgency hint the first window, it should then have focus
        with qtbot.waitSignal(qutewm.window_focused):
            qapp.alert(window_a)
        qtbot.wait(self.WAIT_DELAY)
        assert window_a.isActiveWindow()

    def test_focus_on_request(self, qutewm, qtbot, qapp):
        window_a = self.get_window()
        window_b = self.get_window()
        qtbot.addWidget(window_a)
        qtbot.addWidget(window_b)

        # Show the first window, it should then have focus
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused]):
            window_a.show()
        qtbot.wait(self.WAIT_DELAY)
        assert window_a.isActiveWindow()

        # Show the second window, it should then have focus
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused]):
            window_b.show()
        qtbot.wait(self.WAIT_DELAY)
        assert window_b.isActiveWindow()

        # Activate the first window, it should then have focus
        with qtbot.waitSignal(qutewm.window_focused):
            window_a.activateWindow()
        qtbot.wait(self.WAIT_DELAY)
        assert window_a.isActiveWindow()
