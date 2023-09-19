# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
