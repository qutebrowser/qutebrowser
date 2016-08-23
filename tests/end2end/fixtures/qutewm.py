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

"""Fixtures for the qutewm window manager."""

import os
import re
import sys

import pytest
from PyQt5.QtCore import pyqtSignal

from end2end.fixtures import testprocess


class QuteWMProcess(testprocess.Process):

    """Abstraction over a running qutewm instance.

    Signals:
        window_opened: Emitted when a window is opened.
        window_closed: Emitted when a window is closed.
        window_focused: Emitted when a window is focused.
    """

    SCRIPT = 'qutewm_sub'

    window_opened = pyqtSignal(int)
    window_closed = pyqtSignal(int)
    window_focused = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.wm_failed = False
        self._event_re = re.compile(
            r'window (created|closed|activated): \[0x([0-9a-f]+)\]$')

    def _parse_line(self, line):
        self._log(line)
        if 'event loop started' in line:
            self.ready.emit()
        elif 'Another window manager is running, exiting' in line:
            self.wm_failed = True
            self.ready.emit()
        else:
            match = self._event_re.search(line)
            if match:
                signal = {
                    'created': self.window_opened,
                    'closed': self.window_closed,
                    'activated': self.window_focused,
                }[match.group(1)]
                signal.emit(int(match.group(2), 16))
        return line

    def _executable_args(self):
        if hasattr(sys, 'frozen'):
            executable = os.path.join(os.path.dirname(sys.executable),
                                      self.SCRIPT)
            args = []
        else:
            executable = sys.executable
            py_file = os.path.join(os.path.dirname(__file__),
                                   self.SCRIPT + '.py')
            args = [py_file]
        return executable, args

    def _default_args(self):
        return []


@pytest.fixture(scope='session', autouse=True)
def qutewm(qapp):
    """Make sure a qutewm instance is running for this session.

    If qutewm can't be started, this returns None.
    """
    if sys.platform != 'linux':
        yield None
        return

    qutewm = QuteWMProcess()
    qutewm.start()

    if qutewm.wm_failed:
        # even though the subprocess already exited here, we somehow need that
        # terminate call. Otherwise Qt will throw some errors and the tests
        # will fail...:
        #     SystemError: <class 'PyQt5.QtCore.QtMsgType'> returned a result
        #     with an error set
        qutewm.terminate()
        yield None
        return

    yield qutewm
    qutewm.terminate()


@pytest.fixture(autouse=True)
def qutewm_manager(request, qutewm):
    """Fixture to reset qutewm for each test.

    This does nothing if the test does not have the "qutewm" marker set. If the
    marker is set and qutewm is not running, this skips the test.
    """
    if not request.node.get_marker('qutewm'):
        yield
        return
    if qutewm is None:
        pytest.skip('qutewm required but not started')

    qutewm.before_test()
    if qutewm.wm_failed:
        pytest.skip('qutewm required but not started')
    request.node._qutewm_log = qutewm.captured_log
    yield qutewm
    qutewm.after_test()
