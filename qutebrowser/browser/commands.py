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

"""Command dispatcher for TabbedBrowser."""

import os
import shlex
import posixpath
import functools
import xml.etree.ElementTree

from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWidgets import QApplication, QTabBar
from PyQt5.QtCore import Qt, QUrl, QEvent
from PyQt5.QtGui import QClipboard, QKeyEvent
from PyQt5.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebPage
import pygments
import pygments.lexers
import pygments.formatters

from qutebrowser.commands import userscripts, cmdexc, cmdutils, runners
from qutebrowser.config import config, configexc
from qutebrowser.browser import webelem, inspector, urlmarks
from qutebrowser.keyinput import modeman
from qutebrowser.utils import (message, usertypes, log, qtutils, urlutils,
                               objreg, utils)
from qutebrowser.utils.usertypes import KeyMode
from qutebrowser.misc import editor, guiprocess


class CommandDispatcher:

    """Command dispatcher for TabbedBrowser.

    Contains all commands which are related to the current tab.

    We can't simply add these commands to BrowserTab directly and use
    currentWidget() for TabbedBrowser.cmd because at the time
    cmdutils.register() decorators are run, currentWidget() will return None.

    Attributes:
        _editor: The ExternalEditor object.
        _win_id: The window ID the CommandDispatcher is associated with.
        _tabbed_browser: The TabbedBrowser used.
    """

    def __init__(self, win_id, tabbed_browser):
        self._editor = None
        self._win_id = win_id
        self._tabbed_browser = tabbed_browser

    def __repr__(self):
        return utils.get_repr(self)

    def _new_tabbed_browser(self):
        """Get a tabbed-browser from a new window."""
        from qutebrowser.mainwindow import mainwindow
        new_window = mainwindow.MainWindow()
        new_window.show()
        return new_window.tabbed_browser

    def _count(self):
        """Convenience method to get the widget count."""
        return self._tabbed_browser.count()

    def _set_current_index(self, idx):
        """Convenience method to set the current widget index."""
        return self._tabbed_browser.setCurrentIndex(idx)

    def _current_index(self):
        """Convenience method to get the current widget index."""
        return self._tabbed_browser.currentIndex()

    def _current_url(self):
        """Convenience method to get the current url."""
        try:
            return self._tabbed_browser.current_url()
        except qtutils.QtValueError as e:
            msg = "Current URL is invalid"
            if e.reason:
                msg += " ({})".format(e.reason)
            msg += "!"
            raise cmdexc.CommandError(msg)

    def _current_title(self):
        """Convenience method to get the current title."""
        return self._current_widget().title()

    def _current_widget(self):
        """Get the currently active widget from a command."""
        widget = self._tabbed_browser.currentWidget()
        if widget is None:
            raise cmdexc.CommandError("No WebView available yet!")
        return widget

    def _open(self, url, tab=False, background=False, window=False):
        """Helper function to open a page.

        Args:
            url: The URL to open as QUrl.
            tab: Whether to open in a new tab.
            background: Whether to open in the background.
            window: Whether to open in a new window
        """
        urlutils.raise_cmdexc_if_invalid(url)
        tabbed_browser = self._tabbed_browser
        cmdutils.check_exclusive((tab, background, window), 'tbw')
        if window:
            tabbed_browser = self._new_tabbed_browser()
            tabbed_browser.tabopen(url)
        elif tab:
            tabbed_browser.tabopen(url, background=False, explicit=True)
        elif background:
            tabbed_browser.tabopen(url, background=True, explicit=True)
        else:
            widget = self._current_widget()
            widget.openurl(url)

    def _cntwidget(self, count=None):
        """Return a widget based on a count/idx.

        Args:
            count: The tab index, or None.

        Return:
            The current widget if count is None.
            The widget with the given tab ID if count is given.
            None if no widget was found.
        """
        if count is None:
            return self._tabbed_browser.currentWidget()
        elif 1 <= count <= self._count():
            cmdutils.check_overflow(count + 1, 'int')
            return self._tabbed_browser.widget(count - 1)
        else:
            return None

    def _scroll_percent(self, perc=None, count=None, orientation=None):
        """Inner logic for scroll_percent_(x|y).

        Args:
            perc: How many percent to scroll, or None
            count: How many percent to scroll, or None
            orientation: Qt.Horizontal or Qt.Vertical
        """
        if perc is None and count is None:
            perc = 100
        elif perc is None:
            perc = count
        if perc == 0:
            self.scroll('top')
        elif perc == 100:
            self.scroll('bottom')
        else:
            perc = qtutils.check_overflow(perc, 'int', fatal=False)
            frame = self._current_widget().page().currentFrame()
            m = frame.scrollBarMaximum(orientation)
            if m == 0:
                return
            frame.setScrollBarValue(orientation, int(m * perc / 100))

    def _tab_move_absolute(self, idx):
        """Get an index for moving a tab absolutely.

        Args:
            idx: The index to get, as passed as count.
        """
        if idx is None:
            return 0
        elif idx == 0:
            return self._count() - 1
        else:
            return idx - 1

    def _tab_move_relative(self, direction, delta):
        """Get an index for moving a tab relatively.

        Args:
            direction: + or - for relative moving, None for absolute.
            delta: Delta to the current tab.
        """
        if delta is None:
            # We don't set delta to 1 in the function arguments because this
            # gets called from tab_move which has delta set to None by default.
            delta = 1
        if direction == '-':
            return self._current_index() - delta
        elif direction == '+':
            return self._current_index() + delta

    def _tab_focus_last(self):
        """Select the tab which was last focused."""
        try:
            tab = objreg.get('last-focused-tab', scope='window',
                             window=self._win_id)
        except KeyError:
            raise cmdexc.CommandError("No last focused tab!")
        idx = self._tabbed_browser.indexOf(tab)
        if idx == -1:
            raise cmdexc.CommandError("Last focused tab vanished!")
        self._set_current_index(idx)

    def _editor_cleanup(self, oshandle, filename):
        """Clean up temporary file when the editor was closed."""
        try:
            os.close(oshandle)
            os.remove(filename)
        except OSError:
            raise cmdexc.CommandError("Failed to delete tempfile...")

    def _get_selection_override(self, left, right, opposite):
        """Helper function for tab_close to get the tab to select.

        Args:
            left: Force selecting the tab to the left of the current tab.
            right: Force selecting the tab to the right of the current tab.
            opposite: Force selecting the tab in the opposite direction of
                      what's configured in 'tabs->select-on-remove'.

        Return:
            QTabBar.SelectLeftTab, QTabBar.SelectRightTab, or None if no change
            should be made.
        """
        cmdutils.check_exclusive((left, right, opposite), 'lro')
        if left:
            return QTabBar.SelectLeftTab
        elif right:
            return QTabBar.SelectRightTab
        elif opposite:
            conf_selection = config.get('tabs', 'select-on-remove')
            if conf_selection == QTabBar.SelectLeftTab:
                return QTabBar.SelectRightTab
            elif conf_selection == QTabBar.SelectRightTab:
                return QTabBar.SelectLeftTab
            elif conf_selection == QTabBar.SelectPreviousTab:
                raise cmdexc.CommandError(
                    "-o is not supported with 'tabs->select-on-remove' set to "
                    "'previous'!")
        return None

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def tab_close(self, left=False, right=False, opposite=False, count=None):
        """Close the current/[count]th tab.

        Args:
            left: Force selecting the tab to the left of the current tab.
            right: Force selecting the tab to the right of the current tab.
            opposite: Force selecting the tab in the opposite direction of
                      what's configured in 'tabs->select-on-remove'.
            count: The tab index to close, or None
        """
        tab = self._cntwidget(count)
        if tab is None:
            return
        tabbar = self._tabbed_browser.tabBar()
        selection_override = self._get_selection_override(left, right,
                                                          opposite)
        if selection_override is None:
            self._tabbed_browser.close_tab(tab)
        else:
            old_selection_behavior = tabbar.selectionBehaviorOnRemove()
            tabbar.setSelectionBehaviorOnRemove(selection_override)
            self._tabbed_browser.close_tab(tab)
            tabbar.setSelectionBehaviorOnRemove(old_selection_behavior)

    @cmdutils.register(instance='command-dispatcher', name='open',
                       maxsplit=0, scope='window', count='count',
                       completion=[usertypes.Completion.url])
    def openurl(self, url=None, bg=False, tab=False, window=False, count=None):
        """Open a URL in the current/[count]th tab.

        Args:
            url: The URL to open.
            bg: Open in a new background tab.
            tab: Open in a new tab.
            window: Open in a new window.
            count: The tab index to open the URL in, or None.
        """
        if url is None:
            if tab or bg or window:
                url = config.get('general', 'default-page')
            else:
                raise cmdexc.CommandError("No URL given, but -t/-b/-w is not "
                                          "set!")
        else:
            try:
                url = urlutils.fuzzy_url(url)
            except urlutils.InvalidUrlError as e:
                raise cmdexc.CommandError(e)
        if tab or bg or window:
            self._open(url, tab, bg, window)
        else:
            curtab = self._cntwidget(count)
            if curtab is None:
                if count is None:
                    # We want to open a URL in the current tab, but none exists
                    # yet.
                    self._tabbed_browser.tabopen(url)
                else:
                    # Explicit count with a tab that doesn't exist.
                    return
            else:
                curtab.openurl(url)

    @cmdutils.register(instance='command-dispatcher', name='reload',
                       scope='window', count='count')
    def reloadpage(self, force=False, count=None):
        """Reload the current/[count]th tab.

        Args:
            count: The tab index to reload, or None.
            force: Bypass the page cache.
        """
        tab = self._cntwidget(count)
        if tab is not None:
            if force:
                tab.page().triggerAction(QWebPage.ReloadAndBypassCache)
            else:
                tab.reload()

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def stop(self, count=None):
        """Stop loading in the current/[count]th tab.

        Args:
            count: The tab index to stop, or None.
        """
        tab = self._cntwidget(count)
        if tab is not None:
            tab.stop()

    @cmdutils.register(instance='command-dispatcher', name='print',
                       scope='window', count='count')
    def printpage(self, preview=False, count=None):
        """Print the current/[count]th tab.

        Args:
            preview: Show preview instead of printing.
            count: The tab index to print, or None.
        """
        if not qtutils.check_print_compat():
            # WORKAROUND (remove this when we bump the requirements to 5.3.0)
            raise cmdexc.CommandError(
                "Printing on Qt < 5.3.0 on Windows is broken, please upgrade!")
        tab = self._cntwidget(count)
        if tab is not None:
            if preview:
                diag = QPrintPreviewDialog()
                diag.setAttribute(Qt.WA_DeleteOnClose)
                diag.setWindowFlags(diag.windowFlags() |
                                    Qt.WindowMaximizeButtonHint |
                                    Qt.WindowMinimizeButtonHint)
                diag.paintRequested.connect(tab.print)
                diag.exec_()
            else:
                diag = QPrintDialog()
                diag.setAttribute(Qt.WA_DeleteOnClose)
                diag.open(lambda: tab.print(diag.printer()))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_clone(self, bg=False, window=False):
        """Duplicate the current tab.

        Args:
            bg: Open in a background tab.
            window: Open in a new window.

        Return:
            The new QWebView.
        """
        if bg and window:
            raise cmdexc.CommandError("Only one of -b/-w can be given!")
        curtab = self._current_widget()
        cur_title = self._tabbed_browser.page_title(self._current_index())
        # The new tab could be in a new tabbed_browser (e.g. because of
        # tabs-are-windows being set)
        if window:
            new_tabbed_browser = self._new_tabbed_browser()
        else:
            new_tabbed_browser = self._tabbed_browser
        newtab = new_tabbed_browser.tabopen(background=bg, explicit=True)
        new_tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=newtab.win_id)
        idx = new_tabbed_browser.indexOf(newtab)
        new_tabbed_browser.set_page_title(idx, cur_title)
        new_tabbed_browser.setTabIcon(idx, curtab.icon())
        newtab.keep_icon = True
        newtab.setZoomFactor(curtab.zoomFactor())
        history = qtutils.serialize(curtab.history())
        qtutils.deserialize(history, newtab.history())
        return newtab

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_detach(self):
        """Detach the current tab to its own window."""
        url = self._current_url()
        self._open(url, window=True)
        cur_widget = self._current_widget()
        self._tabbed_browser.close_tab(cur_widget)

    def _back_forward(self, tab, bg, window, count, forward):
        """Helper function for :back/:forward."""
        if (not forward and not
                self._current_widget().page().history().canGoBack()):
            raise cmdexc.CommandError("At beginning of history.")
        if (forward and not
                self._current_widget().page().history().canGoForward()):
            raise cmdexc.CommandError("At end of history.")
        if tab or bg or window:
            widget = self.tab_clone(bg, window)
        else:
            widget = self._current_widget()
        for _ in range(count):
            if forward:
                widget.forward()
            else:
                widget.back()

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def back(self, tab=False, bg=False, window=False, count=1):
        """Go back in the history of the current tab.

        Args:
            tab: Go back in a new tab.
            bg: Go back in a background tab.
            window: Go back in a new window.
            count: How many pages to go back.
        """
        self._back_forward(tab, bg, window, count, forward=False)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def forward(self, tab=False, bg=False, window=False, count=1):
        """Go forward in the history of the current tab.

        Args:
            tab: Go forward in a new tab.
            bg: Go forward in a background tab.
            window: Go forward in a new window.
            count: How many pages to go forward.
        """
        self._back_forward(tab, bg, window, count, forward=True)

    def _navigate_incdec(self, url, incdec, tab, background, window):
        """Helper method for :navigate when `where' is increment/decrement.

        Args:
            url: The current url.
            incdec: Either 'increment' or 'decrement'.
            tab: Whether to open the link in a new tab.
            background: Open the link in a new background tab.
            window: Open the link in a new window.
        """
        try:
            new_url = urlutils.incdec_number(url, incdec)
        except urlutils.IncDecError as error:
            raise cmdexc.CommandError(error.msg)
        self._open(new_url, tab, background, window)

    def _navigate_up(self, url, tab, background, window):
        """Helper method for :navigate when `where' is up.

        Args:
            url: The current url.
            tab: Whether to open the link in a new tab.
            background: Open the link in a new background tab.
            window: Open the link in a new window.
        """
        path = url.path()
        if not path or path == '/':
            raise cmdexc.CommandError("Can't go up!")
        new_path = posixpath.join(path, posixpath.pardir)
        url.setPath(new_path)
        self._open(url, tab, background, window)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def navigate(self, where: {'type': ('prev', 'next', 'up', 'increment',
                                        'decrement')},
                 tab=False, bg=False, window=False):
        """Open typical prev/next links or navigate using the URL path.

        This tries to automatically click on typical _Previous Page_ or
        _Next Page_ links using some heuristics.

        Alternatively it can navigate by changing the current URL.

        Args:
            where: What to open.

                - `prev`: Open a _previous_ link.
                - `next`: Open a _next_ link.
                - `up`: Go up a level in the current URL.
                - `increment`: Increment the last number in the URL.
                - `decrement`: Decrement the last number in the URL.

            tab: Open in a new tab.
            bg: Open in a background tab.
            window: Open in a new window.
        """
        cmdutils.check_exclusive((tab, bg, window), 'tbw')
        widget = self._current_widget()
        frame = widget.page().currentFrame()
        url = self._current_url()
        if frame is None:
            raise cmdexc.CommandError("No frame focused!")
        hintmanager = objreg.get('hintmanager', scope='tab', tab='current')
        if where == 'prev':
            hintmanager.follow_prevnext(frame, url, prev=True, tab=tab,
                                        background=bg, window=window)
        elif where == 'next':
            hintmanager.follow_prevnext(frame, url, prev=False, tab=tab,
                                        background=bg, window=window)
        elif where == 'up':
            self._navigate_up(url, tab, bg, window)
        elif where in ('decrement', 'increment'):
            self._navigate_incdec(url, where, tab, bg, window)
        else:
            raise ValueError("Got called with invalid value {} for "
                             "`where'.".format(where))

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window', count='count')
    def scroll_px(self, dx: {'type': float}, dy: {'type': float}, count=1):
        """Scroll the current tab by 'count * dx/dy' pixels.

        Args:
            dx: How much to scroll in x-direction.
            dy: How much to scroll in x-direction.
            count: multiplier
        """
        dx *= count
        dy *= count
        cmdutils.check_overflow(dx, 'int')
        cmdutils.check_overflow(dy, 'int')
        self._current_widget().page().currentFrame().scroll(dx, dy)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window', count='count')
    def scroll(self,
               direction: {'type': (str, float)},
               dy: {'type': float, 'hide': True}=None,
               count=1):
        """Scroll the current tab in the given direction.

        Args:
            direction: In which direction to scroll
                       (up/down/left/right/top/bottom).
            dy: Deprecated argument to support the old dx/dy form.
            count: multiplier
        """
        try:
            # Check for deprecated dx/dy form (like with scroll-px).
            dx = float(direction)
            dy = float(dy)
        except (ValueError, TypeError):
            # Invalid values will get handled later.
            pass
        else:
            message.warning(self._win_id, ":scroll with dx/dy arguments is "
                            "deprecated - use :scroll-px instead!")
            self.scroll_px(dx, dy, count=count)
            return

        fake_keys = {
            'up': Qt.Key_Up,
            'down': Qt.Key_Down,
            'left': Qt.Key_Left,
            'right': Qt.Key_Right,
            'top': Qt.Key_Home,
            'bottom': Qt.Key_End,
            'page-up': Qt.Key_PageUp,
            'page-down': Qt.Key_PageDown,
        }
        try:
            key = fake_keys[direction]
        except KeyError:
            raise cmdexc.CommandError("Invalid value {!r} for direction - "
                                      "expected one of: {}".format(
                                          direction, ', '.join(fake_keys)))
        widget = self._current_widget()
        frame = widget.page().currentFrame()

        press_evt = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, 0, 0, 0)
        release_evt = QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier, 0, 0, 0)

        # Count doesn't make sense with top/bottom
        if direction in ('top', 'bottom'):
            count = 1

        max_min = {
            'up': [Qt.Vertical, frame.scrollBarMinimum],
            'down': [Qt.Vertical, frame.scrollBarMaximum],
            'left': [Qt.Horizontal, frame.scrollBarMinimum],
            'right': [Qt.Horizontal, frame.scrollBarMaximum],
            'page-up': [Qt.Vertical, frame.scrollBarMinimum],
            'page-down': [Qt.Vertical, frame.scrollBarMaximum],
        }

        for _ in range(count):
            # Abort scrolling if the minimum/maximum was reached.
            try:
                qt_dir, getter = max_min[direction]
            except KeyError:
                pass
            else:
                if frame.scrollBarValue(qt_dir) == getter(qt_dir):
                    return

            widget.keyPressEvent(press_evt)
            widget.keyReleaseEvent(release_evt)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window', count='count')
    def scroll_perc(self, perc: {'type': float}=None,
                    horizontal: {'flag': 'x'}=False, count=None):
        """Scroll to a specific percentage of the page.

        The percentage can be given either as argument or as count.
        If no percentage is given, the page is scrolled to the end.

        Args:
            perc: Percentage to scroll.
            horizontal: Scroll horizontally instead of vertically.
            count: Percentage to scroll.
        """
        self._scroll_percent(perc, count,
                             Qt.Horizontal if horizontal else Qt.Vertical)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window', count='count')
    def scroll_page(self, x: {'type': float}, y: {'type': float}, *,
                    top_navigate: {'type': ('prev', 'decrement'),
                                   'metavar': 'ACTION'}=None,
                    bottom_navigate: {'type': ('next', 'increment'),
                                      'metavar': 'ACTION'}=None,
                    count=1):
        """Scroll the frame page-wise.

        Args:
            x: How many pages to scroll to the right.
            y: How many pages to scroll down.
            bottom_navigate: :navigate action (next, increment) to run when
                             scrolling down at the bottom of the page.
            top_navigate: :navigate action (prev, decrement) to run when
                          scrolling up at the top of the page.
            count: multiplier
        """
        frame = self._current_widget().page().currentFrame()
        if not frame.url().isValid():
            # See https://github.com/The-Compiler/qutebrowser/issues/701
            return

        if (bottom_navigate is not None and
                frame.scrollPosition().y() >=
                frame.scrollBarMaximum(Qt.Vertical)):
            self.navigate(bottom_navigate)
            return
        elif top_navigate is not None and frame.scrollPosition().y() == 0:
            self.navigate(top_navigate)
            return

        mult_x = count * x
        mult_y = count * y
        if mult_y.is_integer():
            if mult_y == 0:
                pass
            elif mult_y < 0:
                self.scroll('page-up', count=-int(mult_y))
            elif mult_y > 0:
                self.scroll('page-down', count=int(mult_y))
            mult_y = 0
        if mult_x == 0 and mult_y == 0:
            return
        size = frame.geometry()
        dx = mult_x * size.width()
        dy = mult_y * size.height()
        cmdutils.check_overflow(dx, 'int')
        cmdutils.check_overflow(dy, 'int')
        frame.scroll(dx, dy)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def yank(self, title=False, sel=False, domain=False):
        """Yank the current URL/title to the clipboard or primary selection.

        Args:
            sel: Use the primary selection instead of the clipboard.
            title: Yank the title instead of the URL.
            domain: Yank only the scheme, domain, and port number.
        """
        clipboard = QApplication.clipboard()
        if title:
            s = self._tabbed_browser.page_title(self._current_index())
            what = 'title'
        elif domain:
            port = self._current_url().port()
            s = '{}://{}{}'.format(self._current_url().scheme(),
                                   self._current_url().host(),
                                   ':' + str(port) if port > -1 else '')
            what = 'domain'
        else:
            s = self._current_url().toString(
                QUrl.FullyEncoded | QUrl.RemovePassword)
            what = 'URL'
        if sel and clipboard.supportsSelection():
            mode = QClipboard.Selection
            target = "primary selection"
        else:
            mode = QClipboard.Clipboard
            target = "clipboard"
        log.misc.debug("Yanking to {}: '{}'".format(target, s))
        clipboard.setText(s, mode)
        message.info(self._win_id, "Yanked {} to {}: {}".format(
                     what, target, s))

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def zoom_in(self, count=1):
        """Increase the zoom level for the current tab.

        Args:
            count: How many steps to zoom in.
        """
        tab = self._current_widget()
        try:
            perc = tab.zoom(count)
        except ValueError as e:
            raise cmdexc.CommandError(e)
        message.info(self._win_id, "Zoom level: {}%".format(perc))

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def zoom_out(self, count=1):
        """Decrease the zoom level for the current tab.

        Args:
            count: How many steps to zoom out.
        """
        tab = self._current_widget()
        try:
            perc = tab.zoom(-count)
        except ValueError as e:
            raise cmdexc.CommandError(e)
        message.info(self._win_id, "Zoom level: {}%".format(perc))

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def zoom(self, zoom: {'type': int}=None, count=None):
        """Set the zoom level for the current tab.

        The zoom can be given as argument or as [count]. If neither of both is
        given, the zoom is set to the default zoom.

        Args:
            zoom: The zoom percentage to set.
            count: The zoom percentage to set.
        """
        try:
            default = config.get('ui', 'default-zoom')
            level = cmdutils.arg_or_count(zoom, count, default=default)
        except ValueError as e:
            raise cmdexc.CommandError(e)
        tab = self._current_widget()

        try:
            tab.zoom_perc(level)
        except ValueError as e:
            raise cmdexc.CommandError(e)
        message.info(self._win_id, "Zoom level: {}%".format(level))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_only(self, left=False, right=False):
        """Close all tabs except for the current one.

        Args:
            left: Keep tabs to the left of the current.
            right: Keep tabs to the right of the current.
        """
        cmdutils.check_exclusive((left, right), 'lr')
        cur_idx = self._tabbed_browser.currentIndex()
        assert cur_idx != -1

        for i, tab in enumerate(self._tabbed_browser.widgets()):
            if (i == cur_idx or (left and i < cur_idx) or
                    (right and i > cur_idx)):
                continue
            else:
                self._tabbed_browser.close_tab(tab)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def undo(self):
        """Re-open a closed tab (optionally skipping [count] closed tabs)."""
        try:
            self._tabbed_browser.undo()
        except IndexError:
            raise cmdexc.CommandError("Nothing to undo!")

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def tab_prev(self, count=1):
        """Switch to the previous tab, or switch [count] tabs back.

        Args:
            count: How many tabs to switch back.
        """
        newidx = self._current_index() - count
        if newidx >= 0:
            self._set_current_index(newidx)
        elif config.get('tabs', 'wrap'):
            self._set_current_index(newidx % self._count())
        else:
            raise cmdexc.CommandError("First tab")

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def tab_next(self, count=1):
        """Switch to the next tab, or switch [count] tabs forward.

        Args:
            count: How many tabs to switch forward.
        """
        newidx = self._current_index() + count
        if newidx < self._count():
            self._set_current_index(newidx)
        elif config.get('tabs', 'wrap'):
            self._set_current_index(newidx % self._count())
        else:
            raise cmdexc.CommandError("Last tab")

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def paste(self, sel=False, tab=False, bg=False, window=False):
        """Open a page from the clipboard.

        Args:
            sel: Use the primary selection instead of the clipboard.
            tab: Open in a new tab.
            bg: Open in a background tab.
            window: Open in new window.
        """
        clipboard = QApplication.clipboard()
        if sel and clipboard.supportsSelection():
            mode = QClipboard.Selection
            target = "Primary selection"
        else:
            mode = QClipboard.Clipboard
            target = "Clipboard"
        text = clipboard.text(mode)
        if not text:
            raise cmdexc.CommandError("{} is empty.".format(target))
        log.misc.debug("{} contained: '{}'".format(target, text))
        try:
            url = urlutils.fuzzy_url(text)
        except urlutils.InvalidUrlError as e:
            raise cmdexc.CommandError(e)
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def tab_focus(self, index: {'type': (int, 'last')}=None, count=None):
        """Select the tab given as argument/[count].

        If neither count nor index are given, it behaves like tab-next.

        Args:
            index: The tab index to focus, starting with 1. The special value
                   `last` focuses the last focused tab.
            count: The tab index to focus, starting with 1.
        """
        if index == 'last':
            self._tab_focus_last()
            return
        if index is None and count is None:
            self.tab_next()
            return
        try:
            idx = cmdutils.arg_or_count(index, count, default=1,
                                        countzero=self._count())
        except ValueError as e:
            raise cmdexc.CommandError(e)
        cmdutils.check_overflow(idx + 1, 'int')
        if 1 <= idx <= self._count():
            self._set_current_index(idx - 1)
        else:
            raise cmdexc.CommandError("There's no tab with index {}!".format(
                idx))

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count')
    def tab_move(self, direction: {'type': ('+', '-')}=None, count=None):
        """Move the current tab.

        Args:
            direction: `+` or `-` for relative moving, not given for absolute
                       moving.
            count: If moving absolutely: New position (default: 0)
                   If moving relatively: Offset.
        """
        if direction is None:
            new_idx = self._tab_move_absolute(count)
        elif direction in '+-':
            try:
                new_idx = self._tab_move_relative(direction, count)
            except ValueError:
                raise cmdexc.CommandError("Count must be given for relative "
                                          "moving!")
        else:
            raise cmdexc.CommandError("Invalid direction '{}'!".format(
                direction))
        if not 0 <= new_idx < self._count():
            raise cmdexc.CommandError("Can't move tab to position {}!".format(
                new_idx))
        tab = self._current_widget()
        cur_idx = self._current_index()
        icon = self._tabbed_browser.tabIcon(cur_idx)
        label = self._tabbed_browser.page_title(cur_idx)
        cmdutils.check_overflow(cur_idx, 'int')
        cmdutils.check_overflow(new_idx, 'int')
        self._tabbed_browser.setUpdatesEnabled(False)
        try:
            self._tabbed_browser.removeTab(cur_idx)
            self._tabbed_browser.insertTab(new_idx, tab, icon, label)
            self._set_current_index(new_idx)
        finally:
            self._tabbed_browser.setUpdatesEnabled(True)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    def spawn(self, cmdline, userscript=False, verbose=False, detach=False):
        """Spawn a command in a shell.

        Note the {url} variable which gets replaced by the current URL might be
        useful here.

        Args:
            userscript: Run the command as a userscript.
            verbose: Show notifications when the command started/exited.
            detach: Whether the command should be detached from qutebrowser.
            cmdline: The commandline to execute.
        """
        try:
            cmd, *args = shlex.split(cmdline)
        except ValueError as e:
            raise cmdexc.CommandError("Error while splitting command: "
                                      "{}".format(e))

        args = runners.replace_variables(self._win_id, args)

        log.procs.debug("Executing {} with args {}, userscript={}".format(
            cmd, args, userscript))
        if userscript:
            # ~ expansion is handled by the userscript module.
            self.run_userscript(cmd, *args, verbose=verbose)
        else:
            cmd = os.path.expanduser(cmd)
            proc = guiprocess.GUIProcess(self._win_id, what='command',
                                         verbose=verbose,
                                         parent=self._tabbed_browser)
            if detach:
                proc.start_detached(cmd, args)
            else:
                proc.start(cmd, args)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def home(self):
        """Open main startpage in current tab."""
        self.openurl(config.get('general', 'startpage')[0])

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       deprecated='Use :spawn --userscript instead!')
    def run_userscript(self, cmd, *args: {'nargs': '*'}, verbose=False):
        """Run a userscript given as argument.

        Args:
            cmd: The userscript to run.
            args: Arguments to pass to the userscript.
            verbose: Show notifications when the command started/exited.
        """
        env = {
            'QUTE_MODE': 'command',
        }

        idx = self._current_index()
        if idx != -1:
            env['QUTE_TITLE'] = self._tabbed_browser.page_title(idx)

        webview = self._tabbed_browser.currentWidget()
        if webview is None:
            mainframe = None
        else:
            if webview.hasSelection():
                env['QUTE_SELECTED_TEXT'] = webview.selectedText()
                env['QUTE_SELECTED_HTML'] = webview.selectedHtml()
            mainframe = webview.page().mainFrame()

        try:
            url = self._tabbed_browser.current_url()
        except qtutils.QtValueError:
            pass
        else:
            env['QUTE_URL'] = url.toString(QUrl.FullyEncoded)

        env.update(userscripts.store_source(mainframe))
        userscripts.run(cmd, *args, win_id=self._win_id, env=env,
                        verbose=verbose)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def quickmark_save(self):
        """Save the current page as a quickmark."""
        quickmark_manager = objreg.get('quickmark-manager')
        quickmark_manager.prompt_save(self._win_id, self._current_url())

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0,
                       completion=[usertypes.Completion.quickmark_by_name])
    def quickmark_load(self, name, tab=False, bg=False, window=False):
        """Load a quickmark.

        Args:
            name: The name of the quickmark to load.
            tab: Load the quickmark in a new tab.
            bg: Load the quickmark in a new background tab.
            window: Load the quickmark in a new window.
        """
        try:
            url = objreg.get('quickmark-manager').get(name)
        except urlmarks.Error as e:
            raise cmdexc.CommandError(str(e))
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def bookmark_add(self):
        """Save the current page as a bookmark."""
        bookmark_manager = objreg.get('bookmark-manager')
        url = self._current_url()
        try:
            bookmark_manager.add(url, self._current_title())
        except urlmarks.Error as e:
            raise cmdexc.CommandError(str(e))
        else:
            message.info(self._win_id,
                         "Bookmarked {}!".format(url.toDisplayString()))

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0,
                       completion=[usertypes.Completion.bookmark_by_url])
    def bookmark_load(self, url, tab=False, bg=False, window=False):
        """Load a bookmark.

        Args:
            url: The url of the bookmark to load.
            tab: Load the bookmark in a new tab.
            bg: Load the bookmark in a new background tab.
            window: Load the bookmark in a new window.
        """
        try:
            url = urlutils.fuzzy_url(url)
        except urlutils.InvalidUrlError as e:
            raise cmdexc.CommandError(e)
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    def follow_selected(self, tab=False):
        """Follow the selected text.

        Args:
            tab: Load the selected link in a new tab.
        """
        widget = self._current_widget()
        page = widget.page()
        if not page.hasSelection():
            return
        if QWebSettings.globalSettings().testAttribute(
                QWebSettings.JavascriptEnabled):
            if tab:
                page.open_target = usertypes.ClickTarget.tab
            page.currentFrame().evaluateJavaScript(
                'window.getSelection().anchorNode.parentNode.click()')
        else:
            try:
                selected_element = xml.etree.ElementTree.fromstring(
                    '<html>' + widget.selectedHtml() + '</html>').find('a')
            except xml.etree.ElementTree.ParseError:
                raise cmdexc.CommandError('Could not parse selected element!')

            if selected_element is not None:
                try:
                    url = selected_element.attrib['href']
                except KeyError:
                    raise cmdexc.CommandError('Anchor element without href!')
                url = self._current_url().resolved(QUrl(url))
                self._open(url, tab)

    @cmdutils.register(instance='command-dispatcher', name='inspector',
                       scope='window')
    def toggle_inspector(self):
        """Toggle the web inspector.

        Note: Due a bug in Qt, the inspector will show incorrect request
        headers in the network tab.
        """
        cur = self._current_widget()
        if cur.inspector is None:
            if not config.get('general', 'developer-extras'):
                raise cmdexc.CommandError(
                    "Please enable developer-extras before using the "
                    "webinspector!")
            cur.inspector = inspector.WebInspector()
            cur.inspector.setPage(cur.page())
            cur.inspector.show()
        elif cur.inspector.isVisible():
            cur.inspector.hide()
        else:
            if not config.get('general', 'developer-extras'):
                raise cmdexc.CommandError(
                    "Please enable developer-extras before using the "
                    "webinspector!")
            else:
                cur.inspector.show()

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def download(self, url=None, dest=None):
        """Download a given URL, or current page if no URL given.

        Args:
            url: The URL to download. If not given, download the current page.
            dest: The file path to write the download to, or None to ask.
        """
        download_manager = objreg.get('download-manager', scope='window',
                                      window=self._win_id)
        if url:
            url = urlutils.qurl_from_user_input(url)
            urlutils.raise_cmdexc_if_invalid(url)
            download_manager.get(url, filename=dest)
        else:
            page = self._current_widget().page()
            download_manager.get(self._current_url(), page=page)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       deprecated="Use :download instead.")
    def download_page(self):
        """Download the current page."""
        self.download()

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def view_source(self):
        """Show the source of the current page."""
        # pylint: disable=no-member
        # https://bitbucket.org/logilab/pylint/issue/491/
        widget = self._current_widget()
        if widget.viewing_source:
            raise cmdexc.CommandError("Already viewing source!")
        frame = widget.page().currentFrame()
        html = frame.toHtml()
        lexer = pygments.lexers.HtmlLexer()
        formatter = pygments.formatters.HtmlFormatter(
            full=True, linenos='table')
        highlighted = pygments.highlight(html, lexer, formatter)
        current_url = self._current_url()
        tab = self._tabbed_browser.tabopen(explicit=True)
        tab.setHtml(highlighted, current_url)
        tab.viewing_source = True

    @cmdutils.register(instance='command-dispatcher', name='help',
                       completion=[usertypes.Completion.helptopic],
                       scope='window')
    def show_help(self, tab=False, bg=False, window=False, topic=None):
        r"""Show help about a command or setting.

        Args:
            tab: Open in a new tab.
            bg: Open in a background tab.
            window: Open in a new window.
            topic: The topic to show help for.

                   - :__command__ for commands.
                   - __section__\->__option__ for settings.
        """
        if topic is None:
            path = 'index.html'
        elif topic.startswith(':'):
            command = topic[1:]
            if command not in cmdutils.cmd_dict:
                raise cmdexc.CommandError("Invalid command {}!".format(
                    command))
            path = 'commands.html#{}'.format(command)
        elif '->' in topic:
            parts = topic.split('->')
            if len(parts) != 2:
                raise cmdexc.CommandError("Invalid help topic {}!".format(
                    topic))
            try:
                config.get(*parts)
            except configexc.NoSectionError:
                raise cmdexc.CommandError("Invalid section {}!".format(
                    parts[0]))
            except configexc.NoOptionError:
                raise cmdexc.CommandError("Invalid option {}!".format(
                    parts[1]))
            path = 'settings.html#{}'.format(topic.replace('->', '-'))
        else:
            raise cmdexc.CommandError("Invalid help topic {}!".format(topic))
        url = QUrl('qute://help/{}'.format(path))
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher',
                       modes=[KeyMode.insert], hide=True, scope='window')
    def open_editor(self):
        """Open an external editor with the currently selected form field.

        The editor which should be launched can be configured via the
        `general -> editor` config option.
        """
        frame = self._current_widget().page().currentFrame()
        try:
            elem = webelem.focus_elem(frame)
        except webelem.IsNullError:
            raise cmdexc.CommandError("No element focused!")
        if not elem.is_editable(strict=True):
            raise cmdexc.CommandError("Focused element is not editable!")
        if elem.is_content_editable():
            text = str(elem)
        else:
            text = elem.evaluateJavaScript('this.value')
        self._editor = editor.ExternalEditor(
            self._win_id, self._tabbed_browser)
        self._editor.editing_finished.connect(
            functools.partial(self.on_editing_finished, elem))
        self._editor.edit(text)

    def on_editing_finished(self, elem, text):
        """Write the editor text into the form field and clean up tempfile.

        Callback for GUIProcess when the editor was closed.

        Args:
            elem: The WebElementWrapper which was modified.
            text: The new text to insert.
        """
        try:
            if elem.is_content_editable():
                log.misc.debug("Filling element {} via setPlainText.".format(
                    elem.debug_text()))
                elem.setPlainText(text)
            else:
                log.misc.debug("Filling element {} via javascript.".format(
                    elem.debug_text()))
                text = webelem.javascript_escape(text)
                elem.evaluateJavaScript("this.value='{}'".format(text))
        except webelem.IsNullError:
            raise cmdexc.CommandError("Element vanished while editing!")

    def _clear_search(self, view, text):
        """Clear search string/highlights for the given view.

        This does nothing if the view's search text is the same as the given
        text.
        """
        if view.search_text is not None and view.search_text != text:
            # We first clear the marked text, then the highlights
            view.search('', 0)
            view.search('', QWebPage.HighlightAllOccurrences)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    def search(self, text="", reverse=False):
        """Search for a text on the current page. With no text, clear results.

        Args:
            text: The text to search for.
            reverse: Reverse search direction.
        """
        view = self._current_widget()
        self._clear_search(view, text)
        flags = 0
        ignore_case = config.get('general', 'ignore-case')
        if ignore_case == 'smart':
            if not text.islower():
                flags |= QWebPage.FindCaseSensitively
        elif not ignore_case:
            flags |= QWebPage.FindCaseSensitively
        if config.get('general', 'wrap-search'):
            flags |= QWebPage.FindWrapsAroundDocument
        if reverse:
            flags |= QWebPage.FindBackward
        # We actually search *twice* - once to highlight everything, then again
        # to get a mark so we can navigate.
        view.search(text, flags)
        view.search(text, flags | QWebPage.HighlightAllOccurrences)
        view.search_text = text
        view.search_flags = flags
        self._tabbed_browser.search_text = text
        self._tabbed_browser.search_flags = flags

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window', count='count')
    def search_next(self, count=1):
        """Continue the search to the ([count]th) next term.

        Args:
            count: How many elements to ignore.
        """
        view = self._current_widget()

        self._clear_search(view, self._tabbed_browser.search_text)

        if self._tabbed_browser.search_text is not None:
            view.search_text = self._tabbed_browser.search_text
            view.search_flags = self._tabbed_browser.search_flags
            view.search(view.search_text,
                        view.search_flags | QWebPage.HighlightAllOccurrences)
            for _ in range(count):
                view.search(view.search_text, view.search_flags)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window', count='count')
    def search_prev(self, count=1):
        """Continue the search to the ([count]th) previous term.

        Args:
            count: How many elements to ignore.
        """
        view = self._current_widget()
        self._clear_search(view, self._tabbed_browser.search_text)

        if self._tabbed_browser.search_text is not None:
            view.search_text = self._tabbed_browser.search_text
            view.search_flags = self._tabbed_browser.search_flags
            view.search(view.search_text,
                        view.search_flags | QWebPage.HighlightAllOccurrences)
        # The int() here serves as a QFlags constructor to create a copy of the
        # QFlags instance rather as a reference. I don't know why it works this
        # way, but it does.
        flags = int(view.search_flags)
        if flags & QWebPage.FindBackward:
            flags &= ~QWebPage.FindBackward
        else:
            flags |= QWebPage.FindBackward
        for _ in range(count):
            view.search(view.search_text, flags)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_next_line(self, count=1):
        """Move the cursor or selection to the next line.

        Args:
            count: How many lines to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToNextLine
        else:
            act = QWebPage.SelectNextLine
        for _ in range(count):
            webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_prev_line(self, count=1):
        """Move the cursor or selection to the prev line.

        Args:
            count: How many lines to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToPreviousLine
        else:
            act = QWebPage.SelectPreviousLine
        for _ in range(count):
            webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_next_char(self, count=1):
        """Move the cursor or selection to the next char.

        Args:
            count: How many lines to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToNextChar
        else:
            act = QWebPage.SelectNextChar
        for _ in range(count):
            webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_prev_char(self, count=1):
        """Move the cursor or selection to the previous char.

        Args:
            count: How many chars to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToPreviousChar
        else:
            act = QWebPage.SelectPreviousChar
        for _ in range(count):
            webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_end_of_word(self, count=1):
        """Move the cursor or selection to the end of the word.

        Args:
            count: How many words to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToNextWord
        else:
            act = QWebPage.SelectNextWord
        for _ in range(count):
            webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_next_word(self, count=1):
        """Move the cursor or selection to the next word.

        Args:
            count: How many words to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = [QWebPage.MoveToNextWord, QWebPage.MoveToNextChar]
        else:
            act = [QWebPage.SelectNextWord, QWebPage.SelectNextChar]
        for _ in range(count):
            for a in act:
                webview.triggerPageAction(a)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_prev_word(self, count=1):
        """Move the cursor or selection to the previous word.

        Args:
            count: How many words to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToPreviousWord
        else:
            act = QWebPage.SelectPreviousWord
        for _ in range(count):
            webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def move_to_start_of_line(self):
        """Move the cursor or selection to the start of the line."""
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToStartOfLine
        else:
            act = QWebPage.SelectStartOfLine
        webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def move_to_end_of_line(self):
        """Move the cursor or selection to the end of line."""
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToEndOfLine
        else:
            act = QWebPage.SelectEndOfLine
        webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_start_of_next_block(self, count=1):
        """Move the cursor or selection to the start of next block.

        Args:
            count: How many blocks to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = [QWebPage.MoveToEndOfBlock, QWebPage.MoveToNextLine,
                   QWebPage.MoveToStartOfBlock]
        else:
            act = [QWebPage.SelectEndOfBlock, QWebPage.SelectNextLine,
                   QWebPage.SelectStartOfBlock]
        for _ in range(count):
            for a in act:
                webview.triggerPageAction(a)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_start_of_prev_block(self, count=1):
        """Move the cursor or selection to the start of previous block.

        Args:
            count: How many blocks to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = [QWebPage.MoveToStartOfBlock, QWebPage.MoveToPreviousLine,
                   QWebPage.MoveToStartOfBlock]
        else:
            act = [QWebPage.SelectStartOfBlock, QWebPage.SelectPreviousLine,
                   QWebPage.SelectStartOfBlock]
        for _ in range(count):
            for a in act:
                webview.triggerPageAction(a)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_end_of_next_block(self, count=1):
        """Move the cursor or selection to the end of next block.

        Args:
            count: How many blocks to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = [QWebPage.MoveToEndOfBlock, QWebPage.MoveToNextLine,
                   QWebPage.MoveToEndOfBlock]
        else:
            act = [QWebPage.SelectEndOfBlock, QWebPage.SelectNextLine,
                   QWebPage.SelectEndOfBlock]
        for _ in range(count):
            for a in act:
                webview.triggerPageAction(a)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window', count='count')
    def move_to_end_of_prev_block(self, count=1):
        """Move the cursor or selection to the end of previous block.

        Args:
            count: How many blocks to move.
        """
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = [QWebPage.MoveToStartOfBlock, QWebPage.MoveToPreviousLine,
                   QWebPage.MoveToEndOfBlock]
        else:
            act = [QWebPage.SelectStartOfBlock, QWebPage.SelectPreviousLine,
                   QWebPage.SelectEndOfBlock]
        for _ in range(count):
            for a in act:
                webview.triggerPageAction(a)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def move_to_start_of_document(self):
        """Move the cursor or selection to the start of the document."""
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToStartOfDocument
        else:
            act = QWebPage.SelectStartOfDocument
        webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def move_to_end_of_document(self):
        """Move the cursor or selection to the end of the document."""
        webview = self._current_widget()
        if not webview.selection_enabled:
            act = QWebPage.MoveToEndOfDocument
        else:
            act = QWebPage.SelectEndOfDocument
        webview.triggerPageAction(act)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def yank_selected(self, sel=False, keep=False):
        """Yank the selected text to the clipboard or primary selection.

        Args:
            sel: Use the primary selection instead of the clipboard.
            keep: If given, stay in visual mode after yanking.
        """
        s = self._current_widget().selectedText()
        if not self._current_widget().hasSelection() or len(s) == 0:
            message.info(self._win_id, "Nothing to yank")
            return

        clipboard = QApplication.clipboard()
        if sel and clipboard.supportsSelection():
            mode = QClipboard.Selection
            target = "primary selection"
        else:
            mode = QClipboard.Clipboard
            target = "clipboard"
        log.misc.debug("Yanking to {}: '{}'".format(target, s))
        clipboard.setText(s, mode)
        message.info(self._win_id, "{} {} yanked to {}".format(
            len(s), "char" if len(s) == 1 else "chars", target))
        if not keep:
            modeman.maybe_leave(self._win_id, KeyMode.caret, "yank selected")

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def toggle_selection(self):
        """Toggle caret selection mode."""
        widget = self._current_widget()
        widget.selection_enabled = not widget.selection_enabled
        mainwindow = objreg.get('main-window', scope='window',
                                window=self._win_id)
        mainwindow.status.set_mode_active(usertypes.KeyMode.caret, True)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def drop_selection(self):
        """Drop selection and keep selection mode enabled."""
        self._current_widget().triggerPageAction(QWebPage.MoveToNextChar)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       count='count', debug=True)
    def debug_webaction(self, action, count=1):
        """Execute a webaction.

        See http://doc.qt.io/qt-5/qwebpage.html#WebAction-enum for the
        available actions.

        Args:
            action: The action to execute, e.g. MoveToNextChar.
            count: How many times to repeat the action.
        """
        member = getattr(QWebPage, action, None)
        if not isinstance(member, QWebPage.WebAction):
            raise cmdexc.CommandError("{} is not a valid web action!".format(
                action))
        view = self._current_widget()
        for _ in range(count):
            view.triggerPageAction(member)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0, no_cmd_split=True)
    def jseval(self, js_code, quiet=False):
        """Evaluate a JavaScript string.

        Args:
            js_code: The string to evaluate.
            quiet: Don't show resulting JS object.
        """
        frame = self._current_widget().page().mainFrame()
        out = frame.evaluateJavaScript(js_code)

        if quiet:
            return

        if out is None:
            # Getting the actual error (if any) seems to be difficult. The
            # error does end up in BrowserPage.javaScriptConsoleMessage(), but
            # distinguishing between :jseval errors and errors from the webpage
            # is not trivial...
            message.info(self._win_id, 'No output or error')
        else:
            # The output can be a string, number, dict, array, etc. But *don't*
            # output too much data, as this will make qutebrowser hang
            out = str(out)
            if len(out) > 5000:
                message.info(self._win_id, out[:5000] + ' [...trimmed...]')
            else:
                message.info(self._win_id, out)
