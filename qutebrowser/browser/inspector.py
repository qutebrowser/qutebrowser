# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import base64
import binascii

from PyQt5.QtWebKitWidgets import QWebInspector

from qutebrowser.utils import log, objreg


class WebInspector(QWebInspector):

    """A customized WebInspector which stores its geometry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._load_state_geometry()

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
