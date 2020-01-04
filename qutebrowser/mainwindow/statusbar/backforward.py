# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Navigation (back/forward) indicator displayed in the statusbar."""

from qutebrowser.mainwindow.statusbar import textbase


class Backforward(textbase.TextBase):

    """Shows navigation indicator (if you can go backward and/or forward)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = False

    def on_tab_cur_url_changed(self, tabs):
        """Called on URL changes."""
        tab = tabs.widget.currentWidget()
        if tab is None:  # pragma: no cover
            self.setText('')
            self.hide()
            return
        self.on_tab_changed(tab)

    def on_tab_changed(self, tab):
        """Update the text based on the given tab."""
        text = ''
        if tab.history.can_go_back():
            text += '<'
        if tab.history.can_go_forward():
            text += '>'
        if text:
            text = '[' + text + ']'
        self.setText(text)
        self.setVisible(bool(text) and self.enabled)
