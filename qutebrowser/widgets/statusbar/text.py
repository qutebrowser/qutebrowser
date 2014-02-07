"""The text part of the statusbar."""

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

import logging
from PyQt5.QtWidgets import QLabel, QSizePolicy


class Text(QLabel):

    """The text part of the status bar.

    Contains several parts (keystring, error, text, scrollperc) which are later
    joined and displayed.

    """

    keystring = ''
    error = ''
    text = ''
    scrollperc = ''

    def __init__(self, bar):
        super().__init__(bar)
        self.setStyleSheet("padding-right: 1px;")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        self.update()

    def set_keystring(self, s):
        """Setter to be used as a Qt slot."""
        self.keystring = s

    def set_perc(self, x, y):
        """Setter to be used as a Qt slot."""
        # pylint: disable=unused-argument
        if y == 0:
            self.scrollperc = '[top]'
        elif y == 100:
            self.scrollperc = '[bot]'
        else:
            self.scrollperc = '[{}%]'.format(y)

    def set_text(self, text):
        """Setter to be used as a Qt slot."""
        logging.debug('Setting text to "{}"'.format(text))
        self.text = text

    def update(self):
        """Update the text displayed."""
        self.setText(' '.join([self.keystring, self.error, self.text,
                               self.scrollperc]))
