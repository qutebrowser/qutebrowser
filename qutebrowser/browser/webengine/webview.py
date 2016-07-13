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
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.config import config
from qutebrowser.utils import log


class WebEngineView(QWebEngineView):

    """Custom QWebEngineView subclass with qutebrowser-specific features."""

    mouse_wheel_zoom = pyqtSignal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPage(WebEnginePage(self))

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


class WebEnginePage(QWebEnginePage):

    """Custom QWebEnginePage subclass with qutebrowser-specific features."""

    certificate_error = pyqtSignal()

    def certificateError(self, error):
        self.certificate_error.emit()
        return super().certificateError(error)

    def javaScriptConsoleMessage(self, level, msg, line, source):
        """Log javascript messages to qutebrowser's log."""
        # FIXME:qtwebengine maybe unify this in the tab api somehow?
        setting = config.get('general', 'log-javascript-console')
        if setting == 'none':
            return

        level_to_logger = {
            QWebEnginePage.InfoMessageLevel: log.js.info,
            QWebEnginePage.WarningMessageLevel: log.js.warning,
            QWebEnginePage.ErrorMessageLevel: log.js.error,
        }
        logstring = "[{}:{}] {}".format(source, line, msg)
        logger = level_to_logger[level]
        logger(logstring)
