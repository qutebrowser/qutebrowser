# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Small window that shows scroll marks in jump_mark mode."""

import html

from PyQt5.QtWidgets import QLabel, QSizePolicy
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt

from qutebrowser.config import stylesheet
from qutebrowser.utils import qtutils, utils, usertypes


class ScrollHintView(QLabel):

    """The view showing hints for scroll marks in the jump_mark mode.

    Attributes:
        _win_id: Window ID of parent.
        _tabbed_browser: TabbedBrowser holding the scroll marks to show.

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

    def __init__(self, win_id, tabbed_browser, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.RichText)
        self._win_id = win_id
        self._tabbed_browser = tabbed_browser
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.hide()
        stylesheet.set_register(self)

    def __repr__(self):
        return utils.get_repr(self, win_id=self._win_id)

    def showEvent(self, e):
        """Adjust the view size when it's freshly shown."""
        self.update_geometry.emit()
        super().showEvent(e)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_entered(self, mode):
        """Show hints if the mode is jump_mark.

        Args:
            mode: The current mode.
        """
        if mode != usertypes.KeyMode.jump_mark:
            return

        try:
            local_marks = self._tabbed_browser.list_local_marks_perc()
        except qtutils.QtValueError:
            local_marks = {}

        text = ''
        marks = sorted(
            ((key, point) for key, point in local_marks.items()),
            key=lambda item: item[1].y()
        )
        for key, point in marks:
            text += (
                "<tr>"
                "<td>{}</td>"
                "<td style='padding-left: 2ex'>({}%, {}%)</td>"
                "</tr>"
            ).format(
                html.escape(key),
                point.x(),
                point.y(),
            )
        text = '<table>{}</table>'.format(text)

        self.setText(text)
        self.adjustSize()
        self.show()

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Hide when jump_mark mode is left."""
        if mode == usertypes.KeyMode.jump_mark:
            self.hide()
