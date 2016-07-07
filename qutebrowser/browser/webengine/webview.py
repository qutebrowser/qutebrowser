# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""The main browser widget for QtWebEngine."""


from PyQt5.QtCore import pyqtSignal, Qt, QPoint
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEngineView
# pylint: enable=no-name-in-module,import-error,useless-suppression


class WebEngineView(QWebEngineView):

    """Custom QWebEngineView subclass with qutebrowser-specific features."""

    mouse_wheel_zoom = pyqtSignal(QPoint)

    def wheelEvent(self, e):
        """Zoom on Ctrl-Mousewheel.

        Args:
            e: The QWheelEvent.
        """
        if e.modifiers() & Qt.ControlModifier:
            e.accept()
            self.mouse_wheel_zoom.emit(e.angleDelta())
        else:
            super().wheelEvent(e)
