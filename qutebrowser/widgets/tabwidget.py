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

from math import ceil
import functools

from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QSize, QRect
from PyQt5.QtWidgets import (QTabWidget, QTabBar, QSizePolicy, QCommonStyle,
                             QStyle, QStylePainter, QStyleOptionTab)
from PyQt5.QtGui import QIcon, QPalette, QColor

import qutebrowser.config.config as config
from qutebrowser.config.style import set_register_stylesheet
from qutebrowser.utils.qt import qt_ensure_valid


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
    """

    def __init__(self, parent):
        super().__init__(parent)
        bar = TabBar()
        self.setTabBar(bar)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        set_register_stylesheet(self)
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)
        bar.setDrawBase(False)
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyle(TabBarStyle(self.style()))

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
        height = self.tabSizeHint(index).height()
        return QSize(1, height)

    def tabSizeHint(self, _index):
        """Override tabSizeHint so all tabs are the same size.

        https://wiki.python.org/moin/PyQt/Customising%20tab%20bars

        Args:
            _index: The index of the tab.

        Return:
            A QSize.
        """
        height = self.fontMetrics().height()
        size = QSize(self.width() / self.count(), height)
        qt_ensure_valid(size)
        return size

    def paintEvent(self, _e):
        """Override paintEvent to draw the tabs like we want to."""
        p = QStylePainter(self)
        tab = QStyleOptionTab()
        selected = self.currentIndex()
        for idx in range(self.count()):
            self.initStyleOption(tab, idx)
            if idx == selected:
                color = config.get('colors', 'tab.bg.selected')
            elif idx % 2:
                color = config.get('colors', 'tab.bg.odd')
            else:
                color = config.get('colors', 'tab.bg.even')
            tab.palette.setColor(QPalette.Window, QColor(color))
            tab.palette.setColor(QPalette.WindowText,
                                 QColor(config.get('colors', 'tab.fg')))
            if tab.rect.right() < 0 or tab.rect.left() > self.width():
                # Don't bother drawing a tab if the entire tab is outside of
                # the visible tab bar.
                continue
            p.drawControl(QStyle.CE_TabBarTab, tab)


class TabBarStyle(QCommonStyle):

    """Qt style used by TabBar to fix some issues with the default one.

    This fixes the following things:
        - Remove the focus rectangle Ubuntu draws on tabs.
        - Force text to be left-aligned even though Qt has "centered"
          hardcoded.

    Unfortunately PyQt doesn't support QProxyStyle, so we need to do this the
    hard way...

    Based on:

    http://stackoverflow.com/a/17294081
    https://code.google.com/p/makehuman/source/browse/trunk/makehuman/lib/qtgui.py

    Attributes:
        _style: The base/"parent" style.
    """

    def __init__(self, style):
        """Initialize all functions we're not overriding.

        This simply calls the corresponding function in self._style.

        Args:
            style: The base/"parent" style.
        """
        self._style = style
        for method in ('drawComplexControl', 'drawItemPixmap',
                       'generatedIconPixmap', 'hitTestComplexControl',
                       'pixelMetric', 'itemPixmapRect', 'itemTextRect',
                       'polish', 'styleHint', 'subControlRect', 'unpolish',
                       'drawPrimitive', 'drawItemText', 'sizeFromContents'):
            target = getattr(self._style, method)
            setattr(self, method, functools.partial(target))
        super().__init__()

    def drawControl(self, element, opt, p, widget=None):
        """Override drawControl to draw odd tabs in a different color.

        Draws the given element with the provided painter with the style
        options specified by option.

        Args:
            element: ControlElement
            option: const QStyleOption *
            painter: QPainter *
            widget: const QWidget *
        """
        if element == QStyle.CE_TabBarTab:
            # We override this so we can control TabBarTabShape/TabBarTabLabel.
            self.drawControl(QStyle.CE_TabBarTabShape, opt, p, widget)
            self.drawControl(QStyle.CE_TabBarTabLabel, opt, p, widget)
        elif element == QStyle.CE_TabBarTabShape:
            # We use super() rather than self._style here because we don't want
            # any sophisticated drawing.
            super().drawControl(QStyle.CE_TabBarTabShape, opt, p, widget)
        elif element == QStyle.CE_TabBarTabLabel:
            p.fillRect(opt.rect, opt.palette.window())
            text_rect, icon_rect = self._tab_layout(opt)
            if not opt.icon.isNull():
                qt_ensure_valid(icon_rect)
                icon_mode = (QIcon.Normal if opt.state & QStyle.State_Enabled
                             else QIcon.Disabled)
                icon_state = (QIcon.On if opt.state & QStyle.State_Selected
                              else QIcon.Off)
                icon = opt.icon.pixmap(opt.iconSize, icon_mode, icon_state)
                p.drawPixmap(icon_rect.x(), icon_rect.y(), icon)
            self._style.drawItemText(p, text_rect,
                                     Qt.AlignLeft | Qt.AlignVCenter,
                                     opt.palette,
                                     opt.state & QStyle.State_Enabled,
                                     opt.text, QPalette.WindowText)
        else:
            # For any other elements we just delegate the work to our real
            # style.
            self._style.drawControl(element, opt, p, widget)

    def pixelMetric(self, metric, option=None, widget=None):
        """Override pixelMetric to not shift the selected tab.

        Args:
            metric: PixelMetric
            option: const QStyleOption *
            widget: const QWidget *

        Return:
            An int.
        """
        if (metric == QStyle.PM_TabBarTabShiftHorizontal or
                metric == QStyle.PM_TabBarTabShiftVertical or
                metric == QStyle.PM_TabBarTabHSpace or
                metric == QStyle.PM_TabBarTabVSpace):
            return 0
        else:
            return self._style.pixelMetric(metric, option, widget)

    def subElementRect(self, sr, opt, widget=None):
        """Override subElementRect to use our own _tab_layout implementation.

        Args:
            sr: SubElement
            opt: QStyleOption
            widget: QWidget

        Return:
            A QRect.
        """
        if sr == QStyle.SE_TabBarTabText:
            text_rect, _icon_rect = self._tab_layout(opt)
            return text_rect
        if (sr == QStyle.SE_TabBarTabLeftButton or
                sr == QStyle.SE_TabBarTabRightButton):
            size = (opt.leftButtonSize if sr == QStyle.SE_TabBarTabLeftButton
                    else opt.rightButtonSize)
            width = size.width()
            height = size.height()
            mid_height = ceil((opt.rect.height() - height) / 2)
            mid_width = (opt.rect.width() - width) / 2
            if sr == QStyle.SE_TabBarTabLeftButton:
                rect = QRect(opt.rect.x(), mid_height, width, height)
            else:
                rect = QRect(opt.rect.right() - width, mid_height, width,
                             height)
            rect = self._style.visualRect(opt.direction, opt.rect, rect)
            return rect
        else:
            return self._style.subElementRect(sr, opt, widget)

    def _tab_layout(self, opt):
        """Compute the text/icon rect from the opt rect.

        This is based on Qt's QCommonStylePrivate::tabLayout
        (qtbase/src/widgets/styles/qcommonstyle.cpp) as we can't use the
        private implementation.

        Args:
            opt: QStyleOptionTab

        Return:
            A (text_rect, icon_rect) tuple (both QRects).
        """
        padding = 4
        icon_rect = QRect()
        text_rect = QRect(opt.rect)
        qt_ensure_valid(text_rect)
        text_rect.adjust(padding, 0, 0, 0)
        if not opt.leftButtonSize.isEmpty():
            text_rect.adjust(opt.leftButtonSize.width(), 0, 0, 0)
        if not opt.rightButtonSize.isEmpty():
            text_rect.adjust(0, 0, -opt.rightButtonSize.width(), 0)
        if not opt.icon.isNull():
            icon_rect = self._get_icon_rect(opt, text_rect)
            text_rect.adjust(icon_rect.width() + padding, 0, 0, 0)
        text_rect = self._style.visualRect(opt.direction, opt.rect, text_rect)
        qt_ensure_valid(text_rect)
        return (text_rect, icon_rect)

    def _get_icon_rect(self, opt, text_rect):
        """Get a QRect for the icon to draw.

        Args:
            opt: QStyleOptionTab
            text_rect: The QRect for the text.

        Return:
            A QRect.
        """
        icon_size = opt.iconSize
        if not icon_size.isValid():
            icon_extent = self._style.pixelMetric(QStyle.PM_SmallIconSize)
            icon_size = QSize(icon_extent, icon_extent)
        icon_mode = (QIcon.Normal if opt.state & QStyle.State_Enabled
                     else QIcon.Disabled)
        icon_state = (QIcon.On if opt.state & QStyle.State_Selected
                      else QIcon.Off)
        tab_icon_size = opt.icon.actualSize(icon_size, icon_mode, icon_state)
        tab_icon_size = QSize(min(tab_icon_size.width(), icon_size.width()),
                              min(tab_icon_size.height(), icon_size.height()))
        icon_rect = QRect(text_rect.left(),
                          text_rect.center().y() - tab_icon_size.height() / 2,
                          tab_icon_size.width(), tab_icon_size.height())
        icon_rect = self._style.visualRect(opt.direction, opt.rect, icon_rect)
        qt_ensure_valid(icon_rect)
        return icon_rect
