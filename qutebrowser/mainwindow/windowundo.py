# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Code for :undo --window."""

import collections
import dataclasses
from typing import MutableSequence, cast, TYPE_CHECKING

from PyQt5.QtCore import QObject, QByteArray

from qutebrowser.config import config
from qutebrowser.mainwindow import mainwindow
from qutebrowser.misc import objects
if TYPE_CHECKING:
    from qutebrowser.mainwindow import tabbedbrowser


instance = cast('WindowUndoManager', None)


@dataclasses.dataclass
class _WindowUndoEntry:

    """Information needed for :undo -w."""

    geometry: QByteArray
    tab_stack: 'tabbedbrowser.UndoStackType'


class WindowUndoManager(QObject):

    """Manager which saves/restores windows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._undos: MutableSequence[_WindowUndoEntry] = collections.deque()
        objects.qapp.window_closing.connect(self._on_window_closing)
        config.instance.changed.connect(self._on_config_changed)

    @config.change_filter('tabs.undo_stack_size')
    def _on_config_changed(self):
        self._update_undo_stack_size()

    def _on_window_closing(self, window):
        if window.tabbed_browser.is_private:
            return

        self._undos.append(_WindowUndoEntry(
            geometry=window.saveGeometry(),
            tab_stack=window.tabbed_browser.undo_stack,
        ))

    def _update_undo_stack_size(self):
        newsize = config.instance.get('tabs.undo_stack_size')
        if newsize < 0:
            newsize = None
        self._undos = collections.deque(self._undos, maxlen=newsize)

    def undo_last_window_close(self):
        """Restore the last window to be closed.

        It will have the same tab and undo stack as when it was closed.
        """
        entry = self._undos.pop()
        window = mainwindow.MainWindow(
            private=False,
            geometry=entry.geometry,
        )
        window.show()
        window.tabbed_browser.undo_stack = entry.tab_stack
        window.tabbed_browser.undo()


def init():
    global instance
    instance = WindowUndoManager(parent=objects.qapp)
