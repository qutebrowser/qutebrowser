# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Text displayed in the statusbar."""

from PyQt5.QtCore import pyqtSlot

import qutebrowser.config.config as config
from qutebrowser.widgets.statusbar.textbase import TextBase


class Text(TextBase):

    """Text displayed in the statusbar.

    Attributes:
        _normaltext: The "permanent" text. Never automatically cleared.
                     Accessed via normaltext property.
        _temptext: The temporary text to display.
                   Accessed via temptext property.
        _jstext: The text javascript wants to display.
                 Accessed via jstext property.

        The temptext is shown from StatusBar when a temporary text or error is
        available. If not, the permanent text is shown.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._normaltext = ''
        self._temptext = ''
        self._jstext = ''

    @property
    def normaltext(self):
        """Getter for normaltext so we can define a setter."""
        return self._normaltext

    @normaltext.setter
    def normaltext(self, val):
        """Setter for normaltext to update text display after setting."""
        self._normaltext = val
        self._update_text()

    @property
    def temptext(self):
        """Getter for temptext so we can define a setter."""
        return self._temptext

    @temptext.setter
    def temptext(self, val):
        """Setter for temptext to update text display after setting."""
        self._temptext = val
        self._update_text()

    @property
    def jstext(self):
        """Getter for jstext so we can define a setter."""
        return self._jstext

    @jstext.setter
    def jstext(self, val):
        """Setter for jstext to update text display after setting."""
        self._jstext = val
        self._update_text()

    def _update_text(self):
        """Update QLabel text when needed."""
        if self.temptext:
            self.setText(self.temptext)
        elif self.jstext and config.get('ui', 'display-statusbar-messages'):
            self.setText(self.jstext)
        elif self.normaltext:
            self.setText(self.normaltext)
        else:
            self.setText('')

    @pyqtSlot(str)
    def on_statusbar_message(self, val):
        """Called when javascript tries to set a statusbar message."""
        self.jstext = val

    @pyqtSlot()
    def on_load_started(self):
        """Clear jstext when page loading started."""
        self.jstext = ''

    @pyqtSlot(int)
    def on_tab_changed(self, idx):
        """Set the correct jstext when the current tab changed."""
        tab = self.sender().widget(idx)
        self.jstext = tab.statusbar_message

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update text if display-statusbar-messages option changed."""
        if (section, option) == ('ui', 'display-statusbar-messages'):
            self._update_text()
