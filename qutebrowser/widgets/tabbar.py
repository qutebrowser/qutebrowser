"""The tab widget used for TabbedBrowser from browser.py."""

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

from PyQt5.QtWidgets import QTabWidget, QSizePolicy
from PyQt5.QtCore import Qt

import qutebrowser.utils.config as config
from qutebrowser.utils.style import Style


class TabWidget(QTabWidget):

    """The tabwidget used for TabbedBrowser."""

    # FIXME there is still some ugly 1px white stripe from somewhere if we do
    # background-color: grey for QTabBar...

    _stylesheet = """
        QTabWidget::pane {{
            position: absolute;
            top: 0px;
        }}

        QTabBar {{
            {font[tabbar]}
        }}

        QTabBar::tab {{
            {color[tab.bg]}
            {color[tab.fg]}
            padding-left: 5px;
            padding-right: 5px;
            padding-top: 0px;
            padding-bottom: 0px;
        }}

        QTabBar::tab:first, QTabBar::tab:middle {{
            border-right: 1px solid {color[tab.seperator]};
        }}

        QTabBar::tab:selected {{
            {color[tab.bg.selected]}
        }}
    """

    def __init__(self, parent):
        # FIXME export some settings (TabPosition, tabsClosable,
        # usesScrollButtons)
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyle(Style(self.style()))
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))
        self.setDocumentMode(True)
        self.setMovable(True)
        self.setElideMode(Qt.ElideRight)
