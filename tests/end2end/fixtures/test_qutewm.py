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
from PyQt5.QtCore import QEvent, pyqtSignal

import pytest

from qutebrowser.utils import qtutils
from end2end.fixtures import qutewm


class Window(QMainWindow):

    """A window class suitable for tests.

    This window provides a activated signal.
    """

    activated = pyqtSignal()

    def changeEvent(self, ev):
        if ev.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.activated.emit()


@pytest.mark.qutewm
class TestQuteWM:

    def test_single_window(self, qutewm, qtbot, qapp):
        window = Window()
        qtbot.addWidget(window)
        with qtbot.waitSignals([qutewm.window_opened, qutewm.window_focused,
                                window.activated]):
            window.show()
        assert window.isActiveWindow()
        with qtbot.waitSignal(qutewm.window_closed):
            window.close()

    def test_qutewm_exits_when_wm_running(self, qtbot):
        new_process = qutewm.QuteWMProcess()
        new_process.start()
        new_process.terminate()
        assert new_process.wm_failed

    @pytest.mark.parametrize('focus_fn', [
        (lambda windows, qapp: windows[1].close()),
        pytest.mark.skipif(
            not qtutils.version_check('5.4.0'),
            (lambda windows, qapp: qapp.alert(windows[0])),
            reason='Urgency hints only work correctly with Qt 5.4',
        ),
        (lambda windows, qapp: windows[0].activateWindow()),
    ], ids=['window close', 'urgency hint', 'activateWindow()'])
    def test_focus_on_urgency_hint(self, qutewm, qtbot, qapp, focus_fn):
        windows = [Window() for _ in range(2)]
        for window in windows:
            qtbot.addWidget(window)

        for window in windows:
            with qtbot.waitSignals([qutewm.window_opened,
                                    qutewm.window_focused,
                                    window.activated]):
                window.show()
            assert window.isActiveWindow()

        with qtbot.waitSignals([qutewm.window_focused, window.activated]):
            focus_fn(windows, qapp)
        assert windows[0].isActiveWindow()
