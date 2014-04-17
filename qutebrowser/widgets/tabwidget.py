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

"""The tab widget used for TabbedBrowser from browser.py."""

from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtWidgets import QTabWidget, QTabBar, QSizePolicy

import qutebrowser.config.config as config
from qutebrowser.config.style import set_register_stylesheet
from qutebrowser.utils.style import Style


class TabWidget(QTabWidget):

    """The tabwidget used for TabbedBrowser.

    Attributes:
        STYLESHEET: The stylesheet template to be used.
    """

    # FIXME there is still some ugly 1px white stripe from somewhere if we do
    # background-color: grey for QTabBar...

    # pylint: disable=unused-argument

    STYLESHEET = """
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
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyle(Style(self.style()))
        set_register_stylesheet(self)
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)
        self._init_config()

    def _init_config(self):
        """Initialize attributes based on the config."""
        position_conv = {
            'north': QTabWidget.North,
            'south': QTabWidget.South,
            'west': QTabWidget.West,
            'east': QTabWidget.East,
        }
        select_conv = {
            'left': QTabBar.SelectLeftTab,
            'right': QTabBar.SelectRightTab,
            'previous': QTabBar.SelectPreviousTab,
        }
        self.setMovable(config.get('tabbar', 'movable'))
        self.setTabsClosable(config.get('tabbar', 'closebuttons'))
        self.setUsesScrollButtons(config.get('tabbar', 'scrollbuttons'))
        posstr = config.get('tabbar', 'position')
        selstr = config.get('tabbar', 'select_on_remove')
        try:
            self.setTabPosition(position_conv[posstr])
            self.tabBar().setSelectionBehaviorOnRemove(select_conv[selstr])
        except KeyError:
            pass

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update attributes when config changed."""
        if section == 'tabbar':
            self._init_config()
