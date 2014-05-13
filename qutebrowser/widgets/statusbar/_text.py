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

from qutebrowser.widgets.statusbar._textbase import TextBase


class Text(TextBase):

    """Text displayed in the statusbar.

    Attributes:
        normaltext: The "permanent" text. Never automatically cleared.
        temptext: The temporary text. Cleared on a keystroke.
        errortext: The error text. Cleared on a keystroke.
        _initializing: True if we're currently in __init__ and no text should
                       be updated yet.

        The errortext has the highest priority, i.e. it will always be shown
        when it is set. The temptext is shown when there is no error, and the
        (permanent) text is shown when there is neither a temporary text nor an
        error.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initializing = True
        self.normaltext = ''
        self.temptext = ''
        self.errortext = ''
        self._initializing = False

    def __setattr__(self, name, val):
        """Overwrite __setattr__ to call _update_text when needed."""
        super().__setattr__(name, val)
        if not name.startswith('_') and not self._initializing:
            self._update_text()

    def _update_text(self):
        """Update QLabel text when needed.

        Called from __setattr__ if a text property changed.
        """
        for text in [self.errortext, self.temptext, self.normaltext]:
            if text:
                self.setText(text)
                break
        else:
            self.setText('')

    @pyqtSlot(str)
    def set_normaltext(self, val):
        """Setter for normaltext, to be used as Qt slot."""
        self.normaltext = val

    @pyqtSlot(str)
    def on_statusbar_message(self, val):
        """Called when javascript tries to set a statusbar message.

        For some reason, this is emitted a lot with an empty string during page
        load, so we currently ignore these and thus don't support clearing the
        message, which is a bit unfortunate...
        """
        if val:
            self.temptext = val

    @pyqtSlot(str)
    def set_temptext(self, val):
        """Setter for temptext, to be used as Qt slot."""
        self.temptext = val
