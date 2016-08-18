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

from end2end.fixtures import qutewm


@pytest.mark.qutewm
class TestQuteWM:

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
        assert window_a.isActiveWindow()

        # Show the second window, it should then have focus
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused]):
            window_b.show()
        assert window_b.isActiveWindow()

        # Close the second window, focus should revert to the first one
        with qtbot.waitSignals([qutewm.window_closed, qutewm.window_focused]):
            window_b.close()
        assert window_a.isActiveWindow()
