# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import collections
import functools

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QSize, QRect, QTimer
from PyQt5.QtWidgets import (QTabWidget, QTabBar, QSizePolicy, QCommonStyle,
                             QStyle, QStylePainter, QStyleOptionTab)
from PyQt5.QtGui import QIcon, QPalette, QColor

from qutebrowser.utils import qtutils, objreg, utils, usertypes
from qutebrowser.config import config
from qutebrowser.browser import webview


PixelMetrics = usertypes.enum('PixelMetrics', ['icon_padding'],
                              start=QStyle.PM_CustomBase, is_int=True)


class TabWidget(QTabWidget):

    """The tab widget used for TabbedBrowser.

    Signals:
        tab_index_changed: Emitted when the current tab was changed.
                           arg 0: The index of the tab which is now focused.
                           arg 1: The total count of tabs.
    """

    tab_index_changed = pyqtSignal(int, int)

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        bar = TabBar(win_id)
        self.setTabBar(bar)
        bar.tabCloseRequested.connect(self.tabCloseRequested)
        bar.tabMoved.connect(functools.partial(
            QTimer.singleShot, 0, self.update_tab_titles))
        bar.currentChanged.connect(self.emit_tab_index_changed)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)
        self.setUsesScrollButtons(True)
        bar.setDrawBase(False)
        self.init_config()
        objreg.get('config').changed.connect(self.init_config)

    @config.change_filter('tabs')
    def init_config(self):
        """Initialize attributes based on the config."""
        tabbar = self.tabBar()
        self.setMovable(config.get('tabs', 'movable'))
        self.setTabsClosable(False)
        position = config.get('tabs', 'position')
        selection_behavior = config.get('tabs', 'select-on-remove')
        self.setTabPosition(position)
        tabbar.vertical = position in (QTabWidget.West, QTabWidget.East)
        tabbar.setSelectionBehaviorOnRemove(selection_behavior)
        tabbar.refresh()

    def set_tab_indicator_color(self, idx, color):
        """Set the tab indicator color.

        Args:
            idx: The tab index.
            color: A QColor.
        """
        bar = self.tabBar()
        bar.set_tab_data(idx, 'indicator-color', color)
        bar.update(bar.tabRect(idx))

    def set_page_title(self, idx, title):
        """Set the tab title user data."""
        self.tabBar().set_tab_data(idx, 'page-title', title)
        self.update_tab_title(idx)

    def page_title(self, idx):
        """Get the tab title user data."""
        return self.tabBar().page_title(idx)

    def update_tab_title(self, idx):
        """Update the tab text for the given tab."""
        widget = self.widget(idx)
        page_title = self.page_title(idx).replace('&', '&&')

        fields = {}
        if widget.load_status == webview.LoadStatus.loading:
            fields['perc'] = '[{}%] '.format(widget.progress)
        else:
            fields['perc'] = ''
        fields['perc_raw'] = widget.progress
        fields['title'] = page_title
        fields['index'] = idx + 1
        fields['id'] = widget.tab_id
        fields['title_sep'] = ' - ' if page_title else ''

        fmt = config.get('tabs', 'title-format')
        self.tabBar().setTabText(idx, fmt.format(**fields))

    @config.change_filter('tabs', 'title-format')
    def update_tab_titles(self):
        """Update all texts."""
        for idx in range(self.count()):
            self.update_tab_title(idx)

    def tabInserted(self, idx):
        """Update titles when a tab was inserted."""
        super().tabInserted(idx)
        self.update_tab_titles()

    def tabRemoved(self, idx):
        """Update titles when a tab was removed."""
        super().tabRemoved(idx)
        self.update_tab_titles()

    def addTab(self, page, icon_or_text, text_or_empty=None):
        """Override addTab to use our own text setting logic.

        Unfortunately QTabWidget::addTab has these two overloads:
            - QWidget * page, const QIcon & icon, const QString & label
            - QWidget * page, const QString & label

        This means we'll get different arguments based on the chosen overload.

        Args:
            page: The QWidget to add.
            icon_or_text: Either the QIcon to add or the label.
            text_or_empty: Either the label or None.

        Return:
            The index of the newly added tab.
        """
        if text_or_empty is None:
            icon = None
            text = icon_or_text
            new_idx = super().addTab(page, '')
        else:
            icon = icon_or_text
            text = text_or_empty
            new_idx = super().addTab(page, icon, '')
        self.set_page_title(new_idx, text)
        return new_idx

    def insertTab(self, idx, page, icon_or_text, text_or_empty=None):
        """Override insertTab to use our own text setting logic.

        Unfortunately QTabWidget::insertTab has these two overloads:
            - int index, QWidget * page, const QIcon & icon,
              const QString & label
            - int index, QWidget * page, const QString & label

        This means we'll get different arguments based on the chosen overload.

        Args:
            idx: Where to insert the widget.
            page: The QWidget to add.
            icon_or_text: Either the QIcon to add or the label.
            text_or_empty: Either the label or None.

        Return:
            The index of the newly added tab.
        """
        if text_or_empty is None:
            icon = None
            text = icon_or_text
            new_idx = super().insertTab(idx, page, '')
        else:
            icon = icon_or_text
            text = text_or_empty
            new_idx = super().insertTab(idx, page, icon, '')
        self.set_page_title(new_idx, text)
        return new_idx

    @pyqtSlot(int)
    def emit_tab_index_changed(self, index):
        """Emit the tab_index_changed signal if the current tab changed."""
        self.tabBar().on_change()
        self.tab_index_changed.emit(index, self.count())


class TabBar(QTabBar):

    """Custom tab bar with our own style.

    FIXME: Dragging tabs doesn't look as nice as it does in QTabBar.  However,
    fixing this would be a lot of effort, so we'll postpone it until we're
    reimplementing drag&drop for other reasons.

    https://github.com/The-Compiler/qutebrowser/issues/126

    Attributes:
        vertical: When the tab bar is currently vertical.
        win_id: The window ID this TabBar belongs to.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self.setStyle(TabBarStyle(self.style()))
        self.set_font()
        config_obj = objreg.get('config')
        config_obj.changed.connect(self.set_font)
        self.vertical = False
        self._auto_hide_timer = QTimer()
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.setInterval(
            config.get('tabs', 'show-switching-delay'))
        self._auto_hide_timer.timeout.connect(self._tabhide)
        self.setAutoFillBackground(True)
        self.set_colors()
        config_obj.changed.connect(self.set_colors)
        QTimer.singleShot(0, self._tabhide)
        config_obj.changed.connect(self.on_tab_colors_changed)
        config_obj.changed.connect(self.on_show_switching_delay_changed)
        config_obj.changed.connect(self.tabs_show)

    def __repr__(self):
        return utils.get_repr(self, count=self.count())

    @config.change_filter('tabs', 'show')
    def tabs_show(self):
        """Hide or show tab bar if needed when tabs->show got changed."""
        self._tabhide()

    @config.change_filter('tabs', 'show-switching-delay')
    def on_show_switching_delay_changed(self):
        """Set timer interval when tabs->show-switching-delay got changed."""
        self._auto_hide_timer.setInterval(
            config.get('tabs', 'show-switching-delay'))

    def on_change(self):
        """Show tab bar when current tab got changed."""
        show = config.get('tabs', 'show')
        if show == 'switching':
            self.show()
            self._auto_hide_timer.start()

    def _tabhide(self):
        """Hide the tab bar if needed."""
        show = config.get('tabs', 'show')
        show_never = show == 'never'
        switching = show == 'switching'
        multiple = show == 'multiple'
        if show_never or (multiple and self.count() == 1) or switching:
            self.hide()
        else:
            self.show()

    def set_tab_data(self, idx, key, value):
        """Set tab data as a dictionary."""
        if not 0 <= idx < self.count():
            raise IndexError("Tab index ({}) out of range ({})!".format(
                idx, self.count()))
        data = self.tabData(idx)
        if data is None:
            data = {}
        data[key] = value
        self.setTabData(idx, data)

    def tab_data(self, idx, key):
        """Get tab data for a given key."""
        if not 0 <= idx < self.count():
            raise IndexError("Tab index ({}) out of range ({})!".format(
                idx, self.count()))
        data = self.tabData(idx)
        if data is None:
            data = {}
        return data[key]

    def page_title(self, idx):
        """Get the tab title user data.

        Args:
            idx: The tab index to get the title for.
            handle_unset: Whether to return an empty string on KeyError.
        """
        try:
            return self.tab_data(idx, 'page-title')
        except KeyError:
            return ''

    def refresh(self):
        """Properly repaint the tab bar and relayout tabs."""
        # This is a horrible hack, but we need to do this so the underlaying Qt
        # code sets layoutDirty so it actually relayouts the tabs.
        self.setIconSize(self.iconSize())

    @config.change_filter('fonts', 'tabbar')
    def set_font(self):
        """Set the tab bar font."""
        self.setFont(config.get('fonts', 'tabbar'))
        size = self.fontMetrics().height() - 2
        self.setIconSize(QSize(size, size))

    @config.change_filter('colors', 'tabs.bg.bar')
    def set_colors(self):
        """Set the tab bar colors."""
        p = self.palette()
        p.setColor(QPalette.Window, config.get('colors', 'tabs.bg.bar'))
        self.setPalette(p)

    @pyqtSlot(str, str)
    def on_tab_colors_changed(self, section, option):
        """Set the tab colors."""
        if section == 'colors' and option.startswith('tabs.'):
            self.update()

    def mousePressEvent(self, e):
        """Override mousePressEvent to close tabs if configured."""
        button = config.get('tabs', 'close-mouse-button')
        if (e.button() == Qt.RightButton and button == 'right' or
                e.button() == Qt.MiddleButton and button == 'middle'):
            idx = self.tabAt(e.pos())
            if idx != -1:
                e.accept()
                self.tabCloseRequested.emit(idx)
                return
        super().mousePressEvent(e)

    def minimumTabSizeHint(self, index):
        """Set the minimum tab size to indicator/icon/... text.

        Args:
            index: The index of the tab to get a size hint for.

        Return:
            A QSize.
        """
        icon = self.tabIcon(index)
        padding = config.get('tabs', 'padding')
        padding_h = padding.left + padding.right
        padding_v = padding.top + padding.bottom
        if icon.isNull():
            icon_size = QSize(0, 0)
        else:
            extent = self.style().pixelMetric(QStyle.PM_TabBarIconSize, None,
                                              self)
            icon_size = icon.actualSize(QSize(extent, extent))
            padding_h += self.style().pixelMetric(
                PixelMetrics.icon_padding, None, self)
        indicator_width = config.get('tabs', 'indicator-width')
        height = self.fontMetrics().height() + padding_v
        width = (self.fontMetrics().width('\u2026') + icon_size.width() +
                 padding_h + indicator_width)
        return QSize(width, height)

    def tabSizeHint(self, index):
        """Override tabSizeHint so all tabs are the same size.

        https://wiki.python.org/moin/PyQt/Customising%20tab%20bars

        Args:
            index: The index of the tab.

        Return:
            A QSize.
        """
        minimum_size = self.minimumTabSizeHint(index)
        height = minimum_size.height()
        if self.vertical:
            confwidth = str(config.get('tabs', 'width'))
            if confwidth.endswith('%'):
                main_window = objreg.get('main-window', scope='window',
                                         window=self._win_id)
                perc = int(confwidth.rstrip('%'))
                width = main_window.width() * perc / 100
            else:
                width = int(confwidth)
            size = QSize(max(minimum_size.width(), width), height)
        elif self.count() == 0:
            # This happens on startup on OS X.
            # We return it directly rather than setting `size' because we don't
            # want to ensure it's valid in this special case.
            return QSize()
        elif self.count() * minimum_size.width() > self.width():
            # If we don't have enough space, we return the minimum size so we
            # get scroll buttons as soon as needed.
            size = minimum_size
        else:
            # If we *do* have enough space, tabs should occupy the whole window
            # width.
            size = QSize(self.width() / self.count(), height)
        qtutils.ensure_valid(size)
        return size

    def paintEvent(self, _e):
        """Override paintEvent to draw the tabs like we want to."""
        p = QStylePainter(self)
        selected = self.currentIndex()
        for idx in range(self.count()):
            tab = QStyleOptionTab()
            self.initStyleOption(tab, idx)
            if idx == selected:
                bg_color = config.get('colors', 'tabs.bg.selected')
                fg_color = config.get('colors', 'tabs.fg.selected')
            elif idx % 2:
                bg_color = config.get('colors', 'tabs.bg.odd')
                fg_color = config.get('colors', 'tabs.fg.odd')
            else:
                bg_color = config.get('colors', 'tabs.bg.even')
                fg_color = config.get('colors', 'tabs.fg.even')
            tab.palette.setColor(QPalette.Window, bg_color)
            tab.palette.setColor(QPalette.WindowText, fg_color)
            try:
                indicator_color = self.tab_data(idx, 'indicator-color')
            except KeyError:
                indicator_color = QColor()
            tab.palette.setColor(QPalette.Base, indicator_color)
            if tab.rect.right() < 0 or tab.rect.left() > self.width():
                # Don't bother drawing a tab if the entire tab is outside of
                # the visible tab bar.
                continue
            p.drawControl(QStyle.CE_TabBarTab, tab)

    def tabInserted(self, idx):
        """Update visibility when a tab was inserted."""
        super().tabInserted(idx)
        self._tabhide()

    def tabRemoved(self, idx):
        """Update visibility when a tab was removed."""
        super().tabRemoved(idx)
        self._tabhide()

    def addTab(self, icon_or_text, text_or_empty=None):
        """Override addTab to use our own text setting logic.

        Unfortunately QTabBar::addTab has these two overloads:
            - const QIcon & icon, const QString & label
            - const QString & label

        This means we'll get different arguments based on the chosen overload.

        Args:
            icon_or_text: Either the QIcon to add or the label.
            text_or_empty: Either the label or None.

        Return:
            The index of the newly added tab.
        """
        if text_or_empty is None:
            icon = None
            text = icon_or_text
            new_idx = super().addTab('')
        else:
            icon = icon_or_text
            text = text_or_empty
            new_idx = super().addTab(icon, '')
        self.set_page_title(new_idx, text)

    def insertTab(self, idx, icon_or_text, text_or_empty=None):
        """Override insertTab to use our own text setting logic.

        Unfortunately QTabBar::insertTab has these two overloads:
            - int index, const QIcon & icon, const QString & label
            - int index, const QString & label

        This means we'll get different arguments based on the chosen overload.

        Args:
            idx: Where to insert the widget.
            icon_or_text: Either the QIcon to add or the label.
            text_or_empty: Either the label or None.

        Return:
            The index of the newly added tab.
        """
        if text_or_empty is None:
            icon = None
            text = icon_or_text
            new_idx = super().InsertTab(idx, '')
        else:
            icon = icon_or_text
            text = text_or_empty
            new_idx = super().insertTab(idx, icon, '')
        self.set_page_title(new_idx, text)

    def wheelEvent(self, e):
        """Override wheelEvent to make the action configurable.

        Args:
            e: The QWheelEvent
        """
        if config.get('tabs', 'mousewheel-tab-switching'):
            super().wheelEvent(e)
        else:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=self._win_id)
            tabbed_browser.wheelEvent(e)


# Used by TabBarStyle._tab_layout().
Layouts = collections.namedtuple('Layouts', ['text', 'icon', 'indicator'])


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
                       'itemPixmapRect', 'itemTextRect',
                       'polish', 'styleHint', 'subControlRect', 'unpolish',
                       'drawItemText', 'sizeFromContents', 'drawPrimitive'):
            target = getattr(self._style, method)
            setattr(self, method, functools.partial(target))
        super().__init__()

    def _draw_indicator(self, layouts, opt, p):
        """Draw the tab indicator.

        Args:
            layouts: The layouts from _tab_layout.
            opt: QStyleOption from drawControl.
            p: QPainter from drawControl.
        """
        color = opt.palette.base().color()
        rect = layouts.indicator
        indicator_width = config.get('tabs', 'indicator-width')
        if color.isValid() and indicator_width != 0:
            p.fillRect(rect, color)

    def _draw_icon(self, layouts, opt, p):
        """Draw the tab icon.

        Args:
            layouts: The layouts from _tab_layout.
            opt: QStyleOption
            p: QPainter
        """
        qtutils.ensure_valid(layouts.icon)
        icon_mode = (QIcon.Normal if opt.state & QStyle.State_Enabled
                     else QIcon.Disabled)
        icon_state = (QIcon.On if opt.state & QStyle.State_Selected
                      else QIcon.Off)
        icon = opt.icon.pixmap(opt.iconSize, icon_mode, icon_state)
        p.drawPixmap(layouts.icon.x(), layouts.icon.y(), icon)

    def drawControl(self, element, opt, p, widget=None):
        """Override drawControl to draw odd tabs in a different color.

        Draws the given element with the provided painter with the style
        options specified by option.

        Args:
            element: ControlElement
            opt: QStyleOption
            p: QPainter
            widget: QWidget
        """
        layouts = self._tab_layout(opt)
        if element == QStyle.CE_TabBarTab:
            # We override this so we can control TabBarTabShape/TabBarTabLabel.
            self.drawControl(QStyle.CE_TabBarTabShape, opt, p, widget)
            self.drawControl(QStyle.CE_TabBarTabLabel, opt, p, widget)
        elif element == QStyle.CE_TabBarTabShape:
            p.fillRect(opt.rect, opt.palette.window())
            self._draw_indicator(layouts, opt, p)
            # We use super() rather than self._style here because we don't want
            # any sophisticated drawing.
            super().drawControl(QStyle.CE_TabBarTabShape, opt, p, widget)
        elif element == QStyle.CE_TabBarTabLabel:
            if not opt.icon.isNull():
                self._draw_icon(layouts, opt, p)
            alignment = Qt.AlignLeft | Qt.AlignVCenter | Qt.TextHideMnemonic
            self._style.drawItemText(p, layouts.text, alignment, opt.palette,
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
        if metric in [QStyle.PM_TabBarTabShiftHorizontal,
                      QStyle.PM_TabBarTabShiftVertical,
                      QStyle.PM_TabBarTabHSpace,
                      QStyle.PM_TabBarTabVSpace,
                      QStyle.PM_TabBarScrollButtonWidth]:
            return 0
        elif metric == PixelMetrics.icon_padding:
            return 4
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
            layouts = self._tab_layout(opt)
            return layouts.text
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
            A Layout namedtuple with two QRects.
        """
        padding = config.get('tabs', 'padding')
        indicator_padding = config.get('tabs', 'indicator-padding')

        text_rect = QRect(opt.rect)
        indicator_rect = QRect(opt.rect)

        qtutils.ensure_valid(text_rect)
        text_rect.adjust(padding.left, padding.top, -padding.right,
                         -padding.bottom)

        indicator_width = config.get('tabs', 'indicator-width')
        if indicator_width == 0:
            indicator_rect = 0
        else:
            qtutils.ensure_valid(indicator_rect)
            indicator_rect.adjust(padding.left + indicator_padding.left,
                                  padding.top + indicator_padding.top,
                                  0,
                                  -(padding.bottom + indicator_padding.bottom))
            indicator_rect.setWidth(indicator_width)

            text_rect.adjust(indicator_width + indicator_padding.left +
                             indicator_padding.right, 0, 0, 0)

        if opt.icon.isNull():
            icon_rect = QRect()
        else:
            icon_padding = self.pixelMetric(PixelMetrics.icon_padding, opt)
            icon_rect = self._get_icon_rect(opt, text_rect)
            text_rect.adjust(icon_rect.width() + icon_padding, 0, 0, 0)

        text_rect = self._style.visualRect(opt.direction, opt.rect, text_rect)
        return Layouts(text=text_rect, icon=icon_rect,
                       indicator=indicator_rect)

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
            icon_extent = self.pixelMetric(QStyle.PM_SmallIconSize)
            icon_size = QSize(icon_extent, icon_extent)
        icon_mode = (QIcon.Normal if opt.state & QStyle.State_Enabled
                     else QIcon.Disabled)
        icon_state = (QIcon.On if opt.state & QStyle.State_Selected
                      else QIcon.Off)
        tab_icon_size = opt.icon.actualSize(icon_size, icon_mode, icon_state)
        tab_icon_size = QSize(min(tab_icon_size.width(), icon_size.width()),
                              min(tab_icon_size.height(), icon_size.height()))
        icon_rect = QRect(text_rect.left(), text_rect.top() + 1,
                          tab_icon_size.width(), tab_icon_size.height())
        icon_rect = self._style.visualRect(opt.direction, opt.rect, icon_rect)
        qtutils.ensure_valid(icon_rect)
        return icon_rect
