# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import typing
import functools
import contextlib

import attr
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, Qt, QSize, QRect, QPoint,
                          QTimer, QUrl)
from PyQt5.QtWidgets import (QTabWidget, QTabBar, QSizePolicy, QCommonStyle,
                             QStyle, QStylePainter, QStyleOptionTab,
                             QStyleFactory, QWidget)
from PyQt5.QtGui import QIcon, QPalette, QColor

from qutebrowser.utils import qtutils, objreg, utils, usertypes, log
from qutebrowser.config import config, stylesheet
from qutebrowser.misc import objects, debugcachestats
from qutebrowser.browser import browsertab


class TabWidget(QTabWidget):

    """The tab widget used for TabbedBrowser.

    Signals:
        tab_index_changed: Emitted when the current tab was changed.
                           arg 0: The index of the tab which is now focused.
                           arg 1: The total count of tabs.
        new_tab_requested: Emitted when a new tab is requested.
    """

    tab_index_changed = pyqtSignal(int, int)
    new_tab_requested = pyqtSignal('QUrl', bool, bool)

    # Strings for controlling the mute/audible text
    MUTE_STRING = '[M] '
    AUDIBLE_STRING = '[A] '

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        bar = TabBar(win_id, self)
        self.setStyle(TabBarStyle())
        self.setTabBar(bar)
        bar.tabCloseRequested.connect(
            self.tabCloseRequested)  # type: ignore[arg-type]
        bar.tabMoved.connect(functools.partial(
            QTimer.singleShot, 0, self.update_tab_titles))
        bar.currentChanged.connect(self._on_current_changed)
        bar.new_tab_requested.connect(self._on_new_tab_requested)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)
        self.setUsesScrollButtons(True)
        bar.setDrawBase(False)
        self._init_config()
        config.instance.changed.connect(self._init_config)

    @config.change_filter('tabs')
    def _init_config(self):
        """Initialize attributes based on the config."""
        tabbar = self.tabBar()
        self.setMovable(True)
        self.setTabsClosable(False)
        position = config.val.tabs.position
        selection_behavior = config.val.tabs.select_on_remove
        self.setTabPosition(position)
        tabbar.vertical = position in [  # type: ignore[attr-defined]
            QTabWidget.West, QTabWidget.East]
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

    def set_tab_pinned(self, tab: QWidget,
                       pinned: bool) -> None:
        """Set the tab status as pinned.

        Args:
            tab: The tab to pin
            pinned: Pinned tab state to set.
        """
        idx = self.indexOf(tab)
        tab.data.pinned = pinned
        self.update_tab_favicon(tab)
        self.update_tab_title(idx)

    def tab_indicator_color(self, idx):
        """Get the tab indicator color for the given index."""
        return self.tabBar().tab_indicator_color(idx)

    def set_page_title(self, idx, title):
        """Set the tab title user data."""
        tabbar = self.tabBar()

        if config.cache['tabs.tooltips']:
            # always show only plain title in tooltips
            tabbar.setTabToolTip(idx, title)

        tabbar.set_tab_data(idx, 'page-title', title)
        self.update_tab_title(idx)

    def page_title(self, idx):
        """Get the tab title user data."""
        return self.tabBar().page_title(idx)

    def update_tab_title(self, idx, field=None):
        """Update the tab text for the given tab.

        Args:
            idx: The tab index to update.
            field: A field name which was updated. If given, the title
                   is only set if the given field is in the template.
        """
        tab = self.widget(idx)
        if tab.data.pinned:
            fmt = config.cache['tabs.title.format_pinned']
        else:
            fmt = config.cache['tabs.title.format']

        if (field is not None and
                (fmt is None or ('{' + field + '}') not in fmt)):
            return

        fields = self.get_tab_fields(idx)
        fields['current_title'] = fields['current_title'].replace('&', '&&')
        fields['index'] = idx + 1

        title = '' if fmt is None else fmt.format(**fields)
        tabbar = self.tabBar()

        # Only change the tab title if it changes, setting the tab title causes
        # a size recalculation which is slow.
        if tabbar.tabText(idx) != title:
            tabbar.setTabText(idx, title)

    def get_tab_fields(self, idx):
        """Get the tab field data."""
        tab = self.widget(idx)
        if tab is None:
            log.misc.debug(  # type: ignore[unreachable]
                "Got None-tab in get_tab_fields!")

        page_title = self.page_title(idx)

        fields = {}
        fields['id'] = tab.tab_id
        fields['current_title'] = page_title
        fields['title_sep'] = ' - ' if page_title else ''
        fields['perc_raw'] = tab.progress()
        fields['backend'] = objects.backend.name
        fields['private'] = ' [Private Mode] ' if tab.is_private else ''
        try:
            if tab.audio.is_muted():
                fields['audio'] = TabWidget.MUTE_STRING
            elif tab.audio.is_recently_audible():
                fields['audio'] = TabWidget.AUDIBLE_STRING
            else:
                fields['audio'] = ''
        except browsertab.WebTabError:
            # Muting is only implemented with QtWebEngine
            fields['audio'] = ''

        if tab.load_status() == usertypes.LoadStatus.loading:
            fields['perc'] = '[{}%] '.format(tab.progress())
        else:
            fields['perc'] = ''

        try:
            url = self.tab_url(idx)
        except qtutils.QtValueError:
            fields['host'] = ''
            fields['current_url'] = ''
            fields['protocol'] = ''
        else:
            fields['host'] = url.host()
            fields['current_url'] = url.toDisplayString()
            fields['protocol'] = url.scheme()

        y = tab.scroller.pos_perc()[1]
        if y is None:
            scroll_pos = '???'
        elif y <= 0:
            scroll_pos = 'top'
        elif y >= 100:
            scroll_pos = 'bot'
        else:
            scroll_pos = '{:2}%'.format(y)

        fields['scroll_pos'] = scroll_pos
        return fields

    @contextlib.contextmanager
    def _toggle_visibility(self):
        """Toggle visibility while running.

        Every single call to setTabText calls the size hinting functions for
        every single tab, which are slow. Since we know we are updating all
        the tab's titles, we can delay this processing by making the tab
        non-visible. To avoid flickering, disable repaint updates whlie we
        work.
        """
        bar = self.tabBar()
        toggle = (self.count() > 10 and
                  not bar.drag_in_progress and
                  bar.isVisible())
        if toggle:
            bar.setUpdatesEnabled(False)
            bar.setVisible(False)

        yield

        if toggle:
            bar.setVisible(True)
            bar.setUpdatesEnabled(True)

    def update_tab_titles(self):
        """Update all texts."""
        with self._toggle_visibility():
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
            text = icon_or_text
            new_idx = super().insertTab(idx, page, '')
        else:
            icon = icon_or_text
            text = text_or_empty
            new_idx = super().insertTab(idx, page, icon, '')
        self.set_page_title(new_idx, text)
        return new_idx

    @pyqtSlot(int)
    def _on_current_changed(self, index):
        """Emit the tab_index_changed signal if the current tab changed."""
        self.tabBar().on_current_changed()
        self.tab_index_changed.emit(index, self.count())

    @pyqtSlot()
    def _on_new_tab_requested(self):
        """Open a new tab."""
        self.new_tab_requested.emit(config.val.url.default_page, False, False)

    def tab_url(self, idx):
        """Get the URL of the tab at the given index.

        Return:
            The tab URL as QUrl.
        """
        tab = self.widget(idx)
        if tab is None:
            url = QUrl()  # type: ignore[unreachable]
        else:
            url = tab.url()
        # It's possible for url to be invalid, but the caller will handle that.
        qtutils.ensure_valid(url)
        return url

    def update_tab_favicon(self, tab: QWidget) -> None:
        """Update favicon of the given tab."""
        idx = self.indexOf(tab)

        if tab.data.should_show_icon():
            self.setTabIcon(idx, tab.icon())
            if config.val.tabs.tabs_are_windows:
                self.window().setWindowIcon(tab.icon())
        else:
            self.setTabIcon(idx, QIcon())
            if config.val.tabs.tabs_are_windows:
                self.window().setWindowIcon(self.window().windowIcon())

    def setTabIcon(self, idx: int, icon: QIcon) -> None:
        """Always show tab icons for pinned tabs in some circumstances."""
        tab = typing.cast(typing.Optional[browsertab.AbstractTab],
                          self.widget(idx))
        if (icon.isNull() and
                config.cache['tabs.favicons.show'] != 'never' and
                config.cache['tabs.pinned.shrink'] and
                not self.tabBar().vertical and
                tab is not None and tab.data.pinned):
            icon = self.style().standardIcon(QStyle.SP_FileIcon)
        super().setTabIcon(idx, icon)


class TabBar(QTabBar):

    """Custom tab bar with our own style.

    FIXME: Dragging tabs doesn't look as nice as it does in QTabBar.  However,
    fixing this would be a lot of effort, so we'll postpone it until we're
    reimplementing drag&drop for other reasons.

    https://github.com/qutebrowser/qutebrowser/issues/126

    Attributes:
        vertical: When the tab bar is currently vertical.
        win_id: The window ID this TabBar belongs to.

    Signals:
        new_tab_requested: Emitted when a new tab is requested.
    """

    STYLESHEET = """
        TabBar {
            background-color: {{ conf.colors.tabs.bar.bg }};
        }
    """

    new_tab_requested = pyqtSignal()

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self.setStyle(TabBarStyle())
        self._set_font()
        config.instance.changed.connect(self._on_config_changed)
        self.vertical = False
        self._auto_hide_timer = QTimer()
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.maybe_hide)
        self._on_show_switching_delay_changed()
        self.setAutoFillBackground(True)
        self.drag_in_progress = False
        stylesheet.set_register(self)
        QTimer.singleShot(0, self.maybe_hide)

    def __repr__(self):
        return utils.get_repr(self, count=self.count())

    def _current_tab(self):
        """Get the current tab object."""
        return self.parent().currentWidget()

    @pyqtSlot(str)
    def _on_config_changed(self, option: str) -> None:
        if option == 'fonts.tabs':
            self._set_font()
        elif option == 'tabs.favicons.scale':
            self._set_icon_size()
        elif option == 'tabs.show_switching_delay':
            self._on_show_switching_delay_changed()
        elif option == 'tabs.show':
            self.maybe_hide()

        if option.startswith('colors.tabs.'):
            self.update()

        # Clear tab size caches when appropriate
        if option in ["tabs.indicator.padding",
                      "tabs.padding",
                      "tabs.indicator.width",
                      "tabs.min_width",
                      "tabs.pinned.shrink"]:
            self._minimum_tab_size_hint_helper.cache_clear()
            self._minimum_tab_height.cache_clear()

    def _on_show_switching_delay_changed(self):
        """Set timer interval when tabs.show_switching_delay got changed."""
        self._auto_hide_timer.setInterval(config.val.tabs.show_switching_delay)

    def on_current_changed(self):
        """Show tab bar when current tab got changed."""
        self.maybe_hide()  # for fullscreen tabs
        if config.val.tabs.show == 'switching':
            self.show()
            self._auto_hide_timer.start()

    @pyqtSlot()
    def maybe_hide(self):
        """Hide the tab bar if needed."""
        show = config.val.tabs.show
        tab = self._current_tab()
        if (show in ['never', 'switching'] or
                (show == 'multiple' and self.count() == 1) or
                (tab and tab.data.fullscreen)):
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

    def tab_indicator_color(self, idx):
        """Get the tab indicator color for the given index."""
        try:
            return self.tab_data(idx, 'indicator-color')
        except KeyError:
            return QColor()

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
        # This is a horrible hack, but we need to do this so the underlying Qt
        # code sets layoutDirty so it actually relayouts the tabs.
        self.setIconSize(self.iconSize())

    def _set_font(self):
        """Set the tab bar font."""
        self.setFont(config.val.fonts.tabs)
        self._set_icon_size()
        # clear tab size cache
        self._minimum_tab_size_hint_helper.cache_clear()
        self._minimum_tab_height.cache_clear()

    def _set_icon_size(self):
        """Set the tab bar favicon size."""
        size = self.fontMetrics().height() - 2
        size = int(size * config.val.tabs.favicons.scale)
        self.setIconSize(QSize(size, size))

    def mouseReleaseEvent(self, e):
        """Override mouseReleaseEvent to know when drags stop."""
        self.drag_in_progress = False
        super().mouseReleaseEvent(e)

    def mousePressEvent(self, e):
        """Override mousePressEvent to close tabs if configured.

        Also keep track of if we are currently in a drag."""
        self.drag_in_progress = True
        button = config.val.tabs.close_mouse_button
        if (e.button() == Qt.RightButton and button == 'right' or
                e.button() == Qt.MiddleButton and button == 'middle'):
            e.accept()
            idx = self.tabAt(e.pos())
            if idx == -1:
                action = config.val.tabs.close_mouse_button_on_bar
                if action == 'ignore':
                    return
                elif action == 'new-tab':
                    self.new_tab_requested.emit()
                    return
                elif action == 'close-current':
                    idx = self.currentIndex()
                elif action == 'close-last':
                    idx = self.count() - 1
            self.tabCloseRequested.emit(idx)
            return
        super().mousePressEvent(e)

    def minimumTabSizeHint(self, index: int, ellipsis: bool = True) -> QSize:
        """Set the minimum tab size to indicator/icon/... text.

        Args:
            index: The index of the tab to get a size hint for.
            ellipsis: Whether to use ellipsis to calculate width
                      instead of the tab's text.
                      Forced to False for pinned tabs.
        Return:
            A QSize of the smallest tab size we can make.
        """
        icon = self.tabIcon(index)
        if icon.isNull():
            icon_width = 0
        else:
            icon_width = min(
                icon.actualSize(self.iconSize()).width(),
                self.iconSize().width()) + TabBarStyle.ICON_PADDING

        pinned = self._tab_pinned(index)
        if not self.vertical and pinned and config.val.tabs.pinned.shrink:
            # Never consider ellipsis an option for horizontal pinned tabs
            ellipsis = False
        return self._minimum_tab_size_hint_helper(self.tabText(index),
                                                  icon_width, ellipsis,
                                                  pinned)

    @debugcachestats.register(name='tab width cache')
    @functools.lru_cache(maxsize=2**9)
    def _minimum_tab_size_hint_helper(self, tab_text: str,
                                      icon_width: int,
                                      ellipsis: bool, pinned: bool) -> QSize:
        """Helper function to cache tab results.

        Config values accessed in here should be added to _on_config_changed to
        ensure cache is flushed when needed.
        """
        text = '\u2026' if ellipsis else tab_text
        # Don't ever shorten if text is shorter than the ellipsis

        def _text_to_width(text):
            # Calculate text width taking into account qt mnemonics
            return self.fontMetrics().size(Qt.TextShowMnemonic, text).width()
        text_width = min(_text_to_width(text),
                         _text_to_width(tab_text))
        padding = config.cache['tabs.padding']
        indicator_width = config.cache['tabs.indicator.width']
        indicator_padding = config.cache['tabs.indicator.padding']
        padding_h = padding.left + padding.right

        # Only add padding if indicator exists
        if indicator_width != 0:
            padding_h += indicator_padding.left + indicator_padding.right
        height = self._minimum_tab_height()
        width = (text_width + icon_width +
                 padding_h + indicator_width)
        min_width = config.cache['tabs.min_width']
        if (not self.vertical and min_width > 0 and
                not pinned or not config.cache['tabs.pinned.shrink']):
            width = max(min_width, width)
        return QSize(width, height)

    @functools.lru_cache(maxsize=1)
    def _minimum_tab_height(self):
        padding = config.cache['tabs.padding']
        return self.fontMetrics().height() + padding.top + padding.bottom

    def _tab_pinned(self, index: int) -> bool:
        """Return True if tab is pinned."""
        if not 0 <= index < self.count():
            raise IndexError("Tab index ({}) out of range ({})!".format(
                index, self.count()))

        widget = self.parent().widget(index)
        if widget is None:
            # This could happen when Qt calls tabSizeHint while initializing
            # tabs.
            return False
        return widget.data.pinned

    def tabSizeHint(self, index: int) -> QSize:
        """Override tabSizeHint to customize qb's tab size.

        https://wiki.python.org/moin/PyQt/Customising%20tab%20bars

        Args:
            index: The index of the tab.

        Return:
            A QSize.
        """
        if self.count() == 0:
            # This happens on startup on macOS.
            # We return it directly rather than setting `size' because we don't
            # want to ensure it's valid in this special case.
            return QSize()

        height = self._minimum_tab_height()
        if self.vertical:
            confwidth = str(config.cache['tabs.width'])
            if confwidth.endswith('%'):
                main_window = objreg.get('main-window', scope='window',
                                         window=self._win_id)
                perc = int(confwidth.rstrip('%'))
                width = main_window.width() * perc / 100
            else:
                width = int(confwidth)
            size = QSize(width, height)
        else:
            if config.cache['tabs.pinned.shrink'] and self._tab_pinned(index):
                # Give pinned tabs the minimum size they need to display their
                # titles, let Qt handle scaling it down if we get too small.
                width = self.minimumTabSizeHint(index, ellipsis=False).width()
            else:
                # Request as much space as possible so we fill the tabbar, let
                # Qt shrink us down. If for some reason (tests, bugs)
                # self.width() gives 0, use a sane min of 10 px
                width = max(self.width(), 10)
                max_width = config.cache['tabs.max_width']
                if max_width > 0:
                    width = min(max_width, width)
            size = QSize(width, height)
        qtutils.ensure_valid(size)
        return size

    def paintEvent(self, event):
        """Override paintEvent to draw the tabs like we want to."""
        p = QStylePainter(self)
        selected = self.currentIndex()
        for idx in range(self.count()):
            if not event.region().intersects(self.tabRect(idx)):
                # Don't repaint if we are outside the requested region
                continue

            tab = QStyleOptionTab()
            self.initStyleOption(tab, idx)

            setting = 'colors.tabs'
            if self._tab_pinned(idx):
                setting += '.pinned'
            if idx == selected:
                setting += '.selected'
            setting += '.odd' if (idx + 1) % 2 else '.even'

            tab.palette.setColor(QPalette.Window,
                                 config.cache[setting + '.bg'])
            tab.palette.setColor(QPalette.WindowText,
                                 config.cache[setting + '.fg'])

            indicator_color = self.tab_indicator_color(idx)
            tab.palette.setColor(QPalette.Base, indicator_color)
            p.drawControl(QStyle.CE_TabBarTab, tab)

    def tabInserted(self, idx):
        """Update visibility when a tab was inserted."""
        super().tabInserted(idx)
        self.maybe_hide()

    def tabRemoved(self, idx):
        """Update visibility when a tab was removed."""
        super().tabRemoved(idx)
        self.maybe_hide()

    def wheelEvent(self, e):
        """Override wheelEvent to make the action configurable.

        Args:
            e: The QWheelEvent
        """
        if config.val.tabs.mousewheel_switching:
            super().wheelEvent(e)
        else:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=self._win_id)
            tabbed_browser.wheelEvent(e)


@attr.s
class Layouts:

    """Layout information for tab.

    Used by TabBarStyle._tab_layout().
    """

    text = attr.ib()
    icon = attr.ib()
    indicator = attr.ib()


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
    """

    ICON_PADDING = 4

    def __init__(self):
        """Initialize all functions we're not overriding.

        This simply calls the corresponding function in self._style.
        """
        self._style = QStyleFactory.create('Fusion')
        for method in ['drawComplexControl', 'drawItemPixmap',
                       'generatedIconPixmap', 'hitTestComplexControl',
                       'itemPixmapRect', 'itemTextRect', 'polish', 'styleHint',
                       'subControlRect', 'unpolish', 'drawItemText',
                       'sizeFromContents', 'drawPrimitive']:
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
        if color.isValid() and rect.isValid():
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
        self._style.drawItemPixmap(p, layouts.icon, Qt.AlignCenter, icon)

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
        if element not in [QStyle.CE_TabBarTab, QStyle.CE_TabBarTabShape,
                           QStyle.CE_TabBarTabLabel]:
            # Let the real style draw it.
            self._style.drawControl(element, opt, p, widget)
            return

        layouts = self._tab_layout(opt)
        if layouts is None:
            log.misc.warning("Could not get layouts for tab!")
            return

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
            if not opt.icon.isNull() and layouts.icon.isValid():
                self._draw_icon(layouts, opt, p)
            alignment = (config.cache['tabs.title.alignment'] |
                         Qt.AlignVCenter | Qt.TextHideMnemonic)
            self._style.drawItemText(p,
                                     layouts.text,
                                     int(alignment),
                                     opt.palette,
                                     bool(opt.state & QStyle.State_Enabled),
                                     opt.text,
                                     QPalette.WindowText)
        else:
            raise ValueError("Invalid element {!r}".format(element))

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
            if layouts is None:
                log.misc.warning("Could not get layouts for tab!")
                return QRect()
            return layouts.text
        elif sr in [QStyle.SE_TabWidgetTabBar,
                    QStyle.SE_TabBarScrollLeftButton]:
            # Handling SE_TabBarScrollLeftButton so the left scroll button is
            # aligned properly. Otherwise, empty space will be shown after the
            # last tab even though the button width is set to 0
            #
            # Need to use super() because we also use super() to render
            # element in drawControl(); otherwise, we may get bit by
            # style differences...
            return super().subElementRect(sr, opt, widget)
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
            A Layout object with two QRects.
        """
        padding = config.cache['tabs.padding']
        indicator_padding = config.cache['tabs.indicator.padding']

        text_rect = QRect(opt.rect)
        if not text_rect.isValid():
            # This happens sometimes according to crash reports, but no idea
            # why...
            return None

        text_rect.adjust(padding.left, padding.top, -padding.right,
                         -padding.bottom)

        indicator_width = config.cache['tabs.indicator.width']
        if indicator_width == 0:
            indicator_rect = QRect()
        else:
            indicator_rect = QRect(opt.rect)
            qtutils.ensure_valid(indicator_rect)
            indicator_rect.adjust(padding.left + indicator_padding.left,
                                  padding.top + indicator_padding.top,
                                  0,
                                  -(padding.bottom + indicator_padding.bottom))
            indicator_rect.setWidth(indicator_width)

            text_rect.adjust(indicator_width + indicator_padding.left +
                             indicator_padding.right, 0, 0, 0)

        icon_rect = self._get_icon_rect(opt, text_rect)
        if icon_rect.isValid():
            text_rect.adjust(
                icon_rect.width() + TabBarStyle.ICON_PADDING, 0, 0, 0)

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
        # reserve space for favicon when tab bar is vertical (issue #1968)
        position = config.cache['tabs.position']
        if (position in [QTabWidget.East, QTabWidget.West] and
                config.cache['tabs.favicons.show'] != 'never'):
            tab_icon_size = icon_size
        else:
            actual_size = opt.icon.actualSize(icon_size, icon_mode, icon_state)
            tab_icon_size = QSize(
                min(actual_size.width(), icon_size.width()),
                min(actual_size.height(), icon_size.height()))

        icon_top = text_rect.center().y() + 1 - tab_icon_size.height() // 2
        icon_rect = QRect(QPoint(text_rect.left(), icon_top), tab_icon_size)
        icon_rect = self._style.visualRect(opt.direction, opt.rect, icon_rect)
        return icon_rect
