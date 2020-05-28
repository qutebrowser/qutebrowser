# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""The ListView to display downloads in."""

import functools
import typing

from PyQt5.QtCore import pyqtSlot, QSize, Qt, QTimer
from PyQt5.QtWidgets import QListView, QSizePolicy, QMenu, QStyleFactory

from qutebrowser.browser import downloads
from qutebrowser.config import stylesheet
from qutebrowser.utils import qtutils, utils
from qutebrowser.qt import sip


def update_geometry(obj):
    """Weird WORKAROUND for some weird PyQt bug (probably).

    This actually should be a method of DownloadView, but for some reason the
    rowsInserted/rowsRemoved signals don't get disconnected from this method
    when the DownloadView is deleted from Qt (e.g. by closing a window).

    Here we check if obj ("self") was deleted and just ignore the event if so.

    Original bug:   https://github.com/qutebrowser/qutebrowser/issues/167
    Workaround bug: https://github.com/qutebrowser/qutebrowser/issues/171
    """
    def _update_geometry():
        """Actually update the geometry if the object still exists."""
        if sip.isdeleted(obj):
            return
        obj.updateGeometry()

    # If we don't use a singleShot QTimer, the geometry isn't updated correctly
    # and won't include the new item.
    QTimer.singleShot(0, _update_geometry)


_ActionListType = typing.MutableSequence[
    typing.Union[
        typing.Tuple[None, None],  # separator
        typing.Tuple[str, typing.Callable[[], None]],
    ]
]


class DownloadView(QListView):

    """QListView which shows currently running downloads as a bar.

    Attributes:
        _menu: The QMenu which is currently displayed.
    """

    STYLESHEET = """
        QListView {
            background-color: {{ conf.colors.downloads.bar.bg }};
            font: {{ conf.fonts.downloads }};
        }

        QListView::item {
            padding-right: 2px;
        }
    """

    def __init__(self, model, parent=None):
        super().__init__(parent)
        if not utils.is_mac:
            self.setStyle(QStyleFactory.create('Fusion'))
        stylesheet.set_register(self)
        self.setResizeMode(QListView.Adjust)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFlow(QListView.LeftToRight)
        self.setSpacing(1)
        self._menu = None
        model.rowsInserted.connect(functools.partial(update_geometry, self))
        model.rowsRemoved.connect(functools.partial(update_geometry, self))
        model.dataChanged.connect(functools.partial(update_geometry, self))
        self.setModel(model)
        self.setWrapping(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.clicked.connect(self.on_clicked)

    def __repr__(self):
        model = self.model()
        if model is None:
            count = 'None'  # type: ignore[unreachable]
        else:
            count = model.rowCount()
        return utils.get_repr(self, count=count)

    @pyqtSlot(bool)
    def on_fullscreen_requested(self, on):
        """Hide/show the downloadview when entering/leaving fullscreen."""
        if on:
            self.hide()
        else:
            self.show()

    @pyqtSlot('QModelIndex')
    def on_clicked(self, index):
        """Handle clicking of an item.

        Args:
            index: The QModelIndex of the clicked item.
        """
        if not index.isValid():
            return
        item = self.model().data(index, downloads.ModelRole.item)
        if item.done and item.successful:
            item.open_file()
            item.remove()

    def _get_menu_actions(
            self,
            item: downloads.AbstractDownloadItem
    ) -> _ActionListType:
        """Get the available context menu actions for a given DownloadItem.

        Args:
            item: The DownloadItem to get the actions for, or None.
        """
        model = self.model()
        actions = []  # type: _ActionListType
        if item is None:
            pass
        elif item.done:
            if item.successful:
                actions.append(("Open", item.open_file))
            else:
                actions.append(("Retry", item.try_retry))
            actions.append(("Remove", item.remove))
        else:
            actions.append(("Cancel", item.cancel))
        if model.can_clear():
            actions.append((None, None))
            actions.append(("Remove all finished", model.download_clear))
        return actions

    @pyqtSlot('QPoint')
    def show_context_menu(self, point):
        """Show the context menu."""
        index = self.indexAt(point)
        if index.isValid():
            item = self.model().data(index, downloads.ModelRole.item)
        else:
            item = None
        self._menu = QMenu(self)
        actions = self._get_menu_actions(item)
        for (name, handler) in actions:
            if name is None and handler is None:
                self._menu.addSeparator()
            else:
                assert name is not None
                assert handler is not None
                action = self._menu.addAction(name)
                action.triggered.connect(handler)
        if actions:
            self._menu.popup(self.viewport().mapToGlobal(point))

    def minimumSizeHint(self):
        """Override minimumSizeHint so the size is correct in a layout."""
        return self.sizeHint()

    def sizeHint(self):
        """Return sizeHint based on the view contents."""
        idx = self.model().last_index()
        bottom = self.visualRect(idx).bottom()
        if bottom != -1:
            margins = self.contentsMargins()
            height = (bottom + margins.top() + margins.bottom() +
                      2 * self.spacing())
            size = QSize(0, height)
        else:
            size = QSize(0, 0)
        qtutils.ensure_valid(size)
        return size
