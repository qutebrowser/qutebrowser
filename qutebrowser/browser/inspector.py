# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Base class for a QtWebKit/QtWebEngine web inspector."""

import base64
import binascii
import typing
import enum

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QCloseEvent, QMouseEvent

from qutebrowser.browser import eventfilter
from qutebrowser.config import configfiles
from qutebrowser.utils import log, usertypes
from qutebrowser.keyinput import modeman
from qutebrowser.misc import miscwidgets, objects


def create(*, splitter: 'miscwidgets.InspectorSplitter',
           win_id: int,
           parent: QWidget = None) -> 'AbstractWebInspector':
    """Get a WebKitInspector/WebEngineInspector.

    Args:
        splitter: InspectorSplitter where the inspector can be placed.
        win_id: The window ID this inspector is associated with.
        parent: The Qt parent to set.
    """
    # Importing modules here so we don't depend on QtWebEngine without the
    # argument and to avoid circular imports.
    if objects.backend == usertypes.Backend.QtWebEngine:
        from qutebrowser.browser.webengine import webengineinspector
        return webengineinspector.WebEngineInspector(splitter, win_id, parent)
    else:
        from qutebrowser.browser.webkit import webkitinspector
        return webkitinspector.WebKitInspector(splitter, win_id, parent)


class Position(enum.Enum):

    """Where the inspector is shown."""

    right = 1
    left = 2
    top = 3
    bottom = 4
    window = 5


class WebInspectorError(Exception):

    """Raised when the inspector could not be initialized."""


class _EventFilter(QObject):

    """Event filter to enter insert mode when inspector was clicked.

    We need to use this with a ChildEventFilter (rather than just overriding
    mousePressEvent) for two reasons:

    - For QtWebEngine, we need to listen for mouse events on its focusProxy(),
      which can change when another page loads (which might be possible with an
      inspector as well?)

    - For QtWebKit, we need to listen for mouse events on the QWebView used by
      the QWebInspector.
    """

    def __init__(self, win_id: int, parent: QObject) -> None:
        super().__init__(parent)
        self._win_id = win_id

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.MouseButtonPress:
            modeman.enter(self._win_id, usertypes.KeyMode.insert,
                          reason='Inspector clicked')
        return False


class AbstractWebInspector(QWidget):

    """A customized WebInspector which stores its geometry.

    Attributes:
        _position: position of the inspector (right/left/top/bottom/window)
        _splitter: InspectorSplitter where the inspector can be placed.

    Signals:
        closed: Emitted when the inspector is closed.
    """

    closed = pyqtSignal()

    def __init__(self, splitter: 'miscwidgets.InspectorSplitter',
                 win_id: int,
                 parent: QWidget = None) -> None:
        super().__init__(parent)
        self._widget = typing.cast(QWidget, None)
        self._layout = miscwidgets.WrapperLayout(self)
        self._splitter = splitter
        self._position = None  # type: typing.Optional[Position]
        self._event_filter = _EventFilter(win_id, parent=self)
        self._child_event_filter = (
            None)  # type: typing.Optional[eventfilter.ChildEventFilter]
        self._win_id = win_id

    def _set_widget(self, widget: QWidget) -> None:
        self._widget = widget
        self._layout.wrap(self, widget)
        self._child_event_filter = eventfilter.ChildEventFilter(
            eventfilter=self._event_filter,
            widget=self._widget,
            win_id=self._win_id,
            parent=self)
        self._widget.installEventFilter(self._child_event_filter)

    def set_position(self, position: typing.Optional[Position]) -> None:
        """Set the position of the inspector. Will close the inspector if position is None."""
        if position != self._position:
            if self._position == Position.window:
                self._save_state_geometry()

            self._position = position

            if position is None:
                self.hide()
                self.deleteLater()
                self.closed.emit()
            elif position == Position.window:
                self.hide()
                self.setParent(None)  # type: ignore
                self._load_state_geometry()
            else:
                self._splitter.set_inspector(self, position)
            self.show()

    def _load_state_geometry(self) -> None:
        """Load the geometry from the state file."""
        try:
            data = configfiles.state['geometry']['inspector']
            geom = base64.b64decode(data, validate=True)
        except KeyError:
            # First start
            pass
        except binascii.Error:
            log.misc.exception("Error while reading geometry")
        else:
            log.init.debug("Loading geometry from {!r}".format(geom))
            ok = self.restoreGeometry(geom)
            if not ok:
                log.init.warning("Error while loading geometry.")

    def _save_state_geometry(self) -> None:
        """Save the geometry to the state file."""
        data = bytes(self.saveGeometry())
        geom = base64.b64encode(data).decode('ASCII')
        configfiles.state['geometry']['inspector'] = geom

    def closeEvent(self, e: QCloseEvent) -> None:
        """Save the window geometry when closed."""
        self.set_position(None)
        super().closeEvent(e)

    def inspect(self, page: QWidget) -> None:
        """Inspect the given QWeb(Engine)Page."""
        raise NotImplementedError
