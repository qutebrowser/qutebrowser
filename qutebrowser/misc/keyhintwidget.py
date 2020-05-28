# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

import html
import fnmatch
import re

from PyQt5.QtWidgets import QLabel, QSizePolicy
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt

from qutebrowser.config import config, stylesheet
from qutebrowser.utils import utils, usertypes
from qutebrowser.misc import objects
from qutebrowser.keyinput import keyutils


class KeyHintView(QLabel):

    """The view showing hints for key bindings based on the current key string.

    Attributes:
        _win_id: Window ID of parent.

    Signals:
        update_geometry: Emitted when this widget should be resized/positioned.
    """

    STYLESHEET = """
        QLabel {
            font: {{ conf.fonts.keyhint }};
            color: {{ conf.colors.keyhint.fg }};
            background-color: {{ conf.colors.keyhint.bg }};
            padding: 6px;
            {% if conf.statusbar.position == 'top' %}
                border-bottom-right-radius: {{ conf.keyhint.radius }}px;
            {% else %}
                border-top-right-radius: {{ conf.keyhint.radius }}px;
            {% endif %}
        }
    """
    update_geometry = pyqtSignal()

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.RichText)
        self._win_id = win_id
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.hide()
        self._show_timer = usertypes.Timer(self, 'keyhint_show')
        self._show_timer.timeout.connect(self.show)
        self._show_timer.setSingleShot(True)
        stylesheet.set_register(self)

    def __repr__(self):
        return utils.get_repr(self, win_id=self._win_id)

    def showEvent(self, e):
        """Adjust the keyhint size when it's freshly shown."""
        self.update_geometry.emit()
        super().showEvent(e)

    @pyqtSlot(str)
    def update_keyhint(self, modename, prefix):
        """Show hints for the given prefix (or hide if prefix is empty).

        Args:
            prefix: The current partial keystring.
        """
        match = re.fullmatch(r'(\d*)(.*)', prefix)
        assert match is not None, prefix

        countstr, prefix = match.groups()
        if not prefix:
            self._show_timer.stop()
            self.hide()
            return

        def blacklisted(keychain):
            return any(fnmatch.fnmatchcase(keychain, glob)
                       for glob in config.val.keyhint.blacklist)

        def takes_count(cmdstr):
            """Return true iff this command can take a count argument."""
            cmdname = cmdstr.split(' ')[0]
            cmd = objects.commands.get(cmdname)
            return cmd and cmd.takes_count()

        bindings_dict = config.key_instance.get_bindings_for(modename)
        bindings = [(k, v) for (k, v) in sorted(bindings_dict.items())
                    if keyutils.KeySequence.parse(prefix).matches(k) and
                    not blacklisted(str(k)) and
                    (takes_count(v) or not countstr)]

        if not bindings:
            self._show_timer.stop()
            return

        # delay so a quickly typed keychain doesn't display hints
        self._show_timer.setInterval(config.val.keyhint.delay)
        self._show_timer.start()
        suffix_color = html.escape(config.val.colors.keyhint.suffix.fg)

        text = ''
        for seq, cmd in bindings:
            text += (
                "<tr>"
                "<td>{}</td>"
                "<td style='color: {}'>{}</td>"
                "<td style='padding-left: 2ex'>{}</td>"
                "</tr>"
            ).format(
                html.escape(prefix),
                suffix_color,
                html.escape(str(seq)[len(prefix):]),
                html.escape(cmd)
            )
        text = '<table>{}</table>'.format(text)

        self.setText(text)
        self.adjustSize()
        self.update_geometry.emit()
