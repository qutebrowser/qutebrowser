# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Customized QWebInspector."""

import os
import base64
import binascii

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QWidget
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEngineView
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.utils import log, objreg
from qutebrowser.misc import miscwidgets


# FIXME:qtwebengine should we move the geometry stuff to some mixin?


class WebInspectorError(Exception):

    """Raised when the inspector could not be initialized."""

    pass


class WebInspector(QWidget):

    """A web inspector for QtWebEngine which stores its geometry."""

    # FIXME:qtwebengine unify this with the WebKit inspector as far as possible

    def __init__(self, parent=None):
        super().__init__(parent)
        self.port = None
        self._view = QWebEngineView()
        self._layout = miscwidgets.WrapperLayout(self._view, self)
        self.setFocusProxy(self._view)
        self._view.setParent(self)
        self._load_state_geometry()

    def load(self):
        """Set up the inspector."""
        envvar = 'QTWEBENGINE_REMOTE_DEBUGGING'
        if envvar not in os.environ:
            raise WebInspectorError(
                "Debugging is not set up correctly. Did you restart after "
                "setting developer-extras?")
        port = int(os.environ[envvar])
        url = QUrl('http://localhost:{}/'.format(port))
        self._view.load(url)

    def closeEvent(self, e):
        """Save the geometry when closed."""
        state_config = objreg.get('state-config')
        data = bytes(self.saveGeometry())
        geom = base64.b64encode(data).decode('ASCII')
        state_config['geometry']['inspector'] = geom
        super().closeEvent(e)

    def _load_state_geometry(self):
        """Load the geometry from the state file."""
        state_config = objreg.get('state-config')
        try:
            data = state_config['geometry']['inspector']
            geom = base64.b64decode(data, validate=True)
        except KeyError:
            # First start
            pass
        except binascii.Error:
            log.misc.exception("Error while reading geometry")
        else:
            log.init.debug("Loading geometry from {}".format(geom))
            ok = self.restoreGeometry(geom)
            if not ok:
                log.init.warning("Error while loading geometry.")
