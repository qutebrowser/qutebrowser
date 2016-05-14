# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Small window that pops up to show hints for possible keystrings.

When a user inputs a key that forms a partial match, this shows a small window
with each possible completion of that keystring and the corresponding command.
It is intended to help discoverability of keybindings.
"""

from PyQt5.QtWidgets import QLabel, QSizePolicy
from PyQt5.QtCore import pyqtSlot, pyqtSignal

from qutebrowser.config import config, style
from qutebrowser.utils import objreg, utils


class KeyHintView(QLabel):

    """The view showing hints for key bindings based on the current key string.

    Attributes:
        _win_id: Window ID of parent.
        _enabled: If False, do not show the window at all
        _suffix_color: Highlight for completions to the current keychain.

    Signals:
        reposition_keyhint: Emitted when this widget should be resized.
    """

    STYLESHEET = """
        QLabel {
            font: {{ font['keyhint'] }};
            color: {{ color['keyhint.fg'] }};
            background-color: {{ color['keyhint.bg'] }};
        }
    """

    reposition_keyhint = pyqtSignal()

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self.set_enabled()
        config = objreg.get('config')
        config.changed.connect(self.set_enabled)
        self._suffix_color = config.get('colors', 'keyhint.fg.suffix')
        style.set_register_stylesheet(self)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.setVisible(False)

    def __repr__(self):
        return utils.get_repr(self)

    @config.change_filter('ui', 'show-keyhints')
    def set_enabled(self):
        """Update self._enabled when the config changed."""
        self._enabled = config.get('ui', 'show-keyhints')
        if not self._enabled: self.setVisible(False)

    def showEvent(self, e):
        """Adjust the keyhint size when it's freshly shown."""
        self.reposition_keyhint.emit()
        super().showEvent(e)

    @pyqtSlot(str)
    def update_keyhint(self, prefix):
        """Show hints for the given prefix (or hide if prefix is empty).

        Args:
            prefix: The current partial keystring.
        """
        if len(prefix) == 0 or not self._enabled:
            self.setVisible(False)
            return

        self.setVisible(True)

        text = ''
        keyconf = objreg.get('key-config')
        # this is only fired in normal mode
        for key, cmd in keyconf.get_bindings_for('normal').items():
            if key.startswith(prefix):
                suffix = "<font color={}>{}</font>".format(self._suffix_color,
                                                           key[len(prefix):])
                text += '{}{}\t<b>{}</b><br>'.format(prefix, suffix, cmd)

        self.setText(text)
        self.adjustSize()
        self.reposition_keyhint.emit()
