# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tab settings displayed in the statusbar."""

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import objreg


class TabSettings(textbase.TextBase):

    """Tab settings displayed in the statusbar."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        objreg.get('domain-manager').domain_settings_changed.connect(self.set_text)

    @pyqtSlot(int, int)
    def set_text(self, tab=None):  # pylint: disable=unused-argument
        """Setter to be used as a Qt slot.

        Args:
            tab: The new tab to display settings for or current tab if
                falsy.
        """
        text=''
        if not tab or not type(tab) == QWebView:
            try:
                tab = objreg.get('tabbed-browser', scope='window',
                              window='current')._now_focused
            except objreg.RegistryUnavailableError:
                tab = None
            if not tab:
                self.setText('[]')
                return
        if tab._widget.settings().testAttribute(QWebSettings.JavascriptEnabled):
            text = text + 'S'
        self.setText('['+text+']')

    @pyqtSlot(object)
    def on_tab_changed(self, tab):
        """Update tab settings text when tab changed."""
        self.set_text(tab)
