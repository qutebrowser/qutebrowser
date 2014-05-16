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

from qutebrowser.widgets.statusbar._textbase import TextBase


class Text(TextBase):

    """Text displayed in the statusbar.

    Attributes:
        normaltext: The "permanent" text. Never automatically cleared.
        temptext: The temporary text to display.
        _initializing: True if we're currently in __init__ and no text should
                       be updated yet.

        The temptext is shown from StatusBar when a temporary text or error is
        available. If not, the permanent text is shown.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initializing = True
        self.normaltext = ''
        self.temptext = ''
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
        for text in [self.temptext, self.normaltext]:
            if text:
                self.setText(text)
                break
        else:
            self.setText('')
