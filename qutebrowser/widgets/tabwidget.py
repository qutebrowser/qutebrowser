# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QSize
from PyQt5.QtWidgets import QTabWidget, QTabBar, QSizePolicy
from PyQt5.QtGui import QIcon, QPixmap

import qutebrowser.config.config as config
from qutebrowser.config.style import set_register_stylesheet
from qutebrowser.utils.style import Style
from qutebrowser.utils.qt import qt_ensure_valid


class EmptyTabIcon(QIcon):

    """An empty icon for a tab.

    Qt somehow cuts text off when padding is used for the tabbar, see
    https://bugreports.qt-project.org/browse/QTBUG-15203

    Until we find a better solution we use this hack of using a simple
    transparent icon to get some padding, because when a real favicon is set,
    the padding seems to be fine...
    """

    def __init__(self):
        pix = QPixmap(2, 16)
        pix.fill(Qt.transparent)
        super().__init__(pix)


class TabWidget(QTabWidget):

    """The tabwidget used for TabbedBrowser.

    Class attributes:
        STYLESHEET: The stylesheet template to be used.
    """

    STYLESHEET = """
        QTabWidget::pane {{
            position: absolute;
            top: 0px;
        }}

        QTabBar {{
            {font[tabbar]}
            {color[tab.bg.bar]}
        }}

        QTabBar::tab {{
            {color[tab.bg]}
            {color[tab.fg]}
            border-right: 2px solid {color[tab.seperator]};
            min-width: {config[tabbar][min-tab-width]}px;
            max-width: {config[tabbar][max-tab-width]}px;
            margin: 0px;
        }}

        QTabBar::tab:selected {{
            {color[tab.bg.selected]}
        }}
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setTabBar(TabBar())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyle(Style(self.style()))
        set_register_stylesheet(self)
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)
        self.tabBar().setDrawBase(False)
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
        self.setTabsClosable(config.get('tabbar', 'close-buttons'))
        self.setUsesScrollButtons(config.get('tabbar', 'scroll-buttons'))
        posstr = config.get('tabbar', 'position')
        selstr = config.get('tabbar', 'select-on-remove')
        self.setTabPosition(position_conv[posstr])
        self.tabBar().setSelectionBehaviorOnRemove(select_conv[selstr])

    @pyqtSlot(str, str)
    def on_config_changed(self, section, _option):
        """Update attributes when config changed."""
        if section == 'tabbar':
            self._init_config()


class TabBar(QTabBar):

    """Custom tabbar to close tabs on right click.

    Signals:
        tab_rightclicked: Emitted when a tab was right-clicked and should be
                          closed. We use this rather than tabCloseRequested
                          because tabCloseRequested is sometimes connected by
                          Qt to the tabwidget and sometimes not, depending on
                          if close buttons are enabled.
                          arg: The tab index to be closed.
    """

    tab_rightclicked = pyqtSignal(int)

    def __repr__(self):
        return '<{} with {} tabs>'.format(self.__class__.__name__,
                                          self.count())

    def mousePressEvent(self, e):
        """Override mousePressEvent to emit tabCloseRequested on rightclick."""
        if e.button() != Qt.RightButton:
            super().mousePressEvent(e)
            return
        idx = self.tabAt(e.pos())
        if idx == -1:
            super().mousePressEvent(e)
            return
        e.accept()
        if config.get('tabbar', 'close-on-right-click'):
            self.tab_rightclicked.emit(idx)

    def minimumTabSizeHint(self, index):
        """Override minimumTabSizeHint because we want no hard minimum.

        There are two problems with having a hard minimum tab size:
        - When expanding is True, the window will expand without stopping
          on some window managers.
        - We don't want the main window to get bigger with many tabs. If
          nothing else helps, we *do* want the tabs to get smaller instead
          of enforcing a minimum window size.

        Args:
            index: The index of the tab to get a sizehint for.

        Return:
            A QSize.
        """
        height = super().tabSizeHint(index).height()
        return QSize(1, height)

    def tabSizeHint(self, index):
        """Override tabSizeHint so all tabs are the same size.

        https://wiki.python.org/moin/PyQt/Customising%20tab%20bars
        """
        if config.get('tabbar', 'expand'):
            height = super().tabSizeHint(index).height()
            size = QSize(self.width() / self.count(), height)
        else:
            size = super().tabSizeHint(index)
        qt_ensure_valid(size)
        return size
