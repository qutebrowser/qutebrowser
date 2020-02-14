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
from PyQt5.QtCore import pyqtSignal

from qutebrowser.config import configfiles
from qutebrowser.utils import log, usertypes
from qutebrowser.misc import miscwidgets, objects


def create(splitter, parent=None):
    """Get a WebKitInspector/WebEngineInspector.

    Args:
        splitter: InspectorSplitter where the inspector can be placed.
        parent: The Qt parent to set.
    """
    # Importing modules here so we don't depend on QtWebEngine without the
    # argument and to avoid circular imports.
    if objects.backend == usertypes.Backend.QtWebEngine:
        from qutebrowser.browser.webengine import webengineinspector
        return webengineinspector.WebEngineInspector(splitter, parent)
    else:
        from qutebrowser.browser.webkit import webkitinspector
        return webkitinspector.WebKitInspector(splitter, parent)


class Position(enum.Enum):

    """Where the inspector is shown."""

    right = 1
    left = 2
    top = 3
    bottom = 4
    window = 5


class WebInspectorError(Exception):

    """Raised when the inspector could not be initialized."""


class AbstractWebInspector(QWidget):

    """A customized WebInspector which stores its geometry.

    Attributes:
        _position: position of the inspector (right/left/top/bottom/window)
        _splitter: InspectorSplitter where the inspector can be placed.

    Signals:
        closed: Emitted when the inspector is closed.
    """

    closed = pyqtSignal()

    def __init__(self, splitter, parent=None):
        super().__init__(parent)
        self._widget = typing.cast(QWidget, None)
        self._layout = miscwidgets.WrapperLayout(self)
        self._splitter = splitter
        self._position = None  # type: typing.Optional[Position]

    def _set_widget(self, widget):
        self._widget = widget
        self._layout.wrap(self, widget)

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
                self.setParent(None)
                self._load_state_geometry()
            else:
                self._splitter.set_inspector(self, position)
            self.show()

    def _load_state_geometry(self):
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

    def _save_state_geometry(self):
        """Save the geometry to the state file."""
        data = bytes(self.saveGeometry())
        geom = base64.b64encode(data).decode('ASCII')
        configfiles.state['geometry']['inspector'] = geom

    def closeEvent(self, e):
        """Save the window geometry when closed."""
        self.set_position(None)
        super().closeEvent(e)

    def inspect(self, page):
        """Inspect the given QWeb(Engine)Page."""
        raise NotImplementedError
