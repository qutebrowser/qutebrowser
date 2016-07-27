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

"""Command dispatcher for TabbedBrowser."""

import os
import os.path
import shlex
import posixpath
import functools

from PyQt5.QtWidgets import QApplication, QTabBar
from PyQt5.QtCore import Qt, QUrl, QEvent
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebPage
try:
    from PyQt5.QtWebEngineWidgets import QWebEnginePage
except ImportError:
    QWebEnginePage = None
import pygments
import pygments.lexers
import pygments.formatters

from qutebrowser.commands import userscripts, cmdexc, cmdutils, runners
from qutebrowser.config import config, configexc
from qutebrowser.browser import urlmarks, browsertab
from qutebrowser.browser.webkit import webelem, inspector, downloads, mhtml
from qutebrowser.keyinput import modeman
from qutebrowser.utils import (message, usertypes, log, qtutils, urlutils,
                               objreg, utils, typing)
from qutebrowser.utils.usertypes import KeyMode
from qutebrowser.misc import editor, guiprocess
from qutebrowser.completion.models import instances, sortfilter


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
            else:  # pragma: no cover
                raise ValueError("Invalid select-on-remove value "
                                 "{!r}!".format(conf_selection))
        return None

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
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
                       maxsplit=0, scope='window')
    @cmdutils.argument('url', completion=usertypes.Completion.url)
    @cmdutils.argument('count', count=True)
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
                # We don't use cmdexc.CommandError here as this can be called
                # async from edit_url
                message.error(self._win_id, str(e))
                return
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
                       scope='window')
    @cmdutils.argument('count', count=True)
    def reloadpage(self, force=False, count=None):
        """Reload the current/[count]th tab.

        Args:
            count: The tab index to reload, or None.
            force: Bypass the page cache.
        """
        tab = self._cntwidget(count)
        if tab is not None:
            tab.reload(force=force)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
    def stop(self, count=None):
        """Stop loading in the current/[count]th tab.

        Args:
            count: The tab index to stop, or None.
        """
        tab = self._cntwidget(count)
        if tab is not None:
            tab.stop()

    @cmdutils.register(instance='command-dispatcher', name='print',
                       scope='window')
    @cmdutils.argument('count', count=True)
    @cmdutils.argument('pdf', flag='f', metavar='file')
    def printpage(self, preview=False, count=None, *, pdf=None):
        """Print the current/[count]th tab.

        Args:
            preview: Show preview instead of printing.
            count: The tab index to print, or None.
            pdf: The file path to write the PDF to.
        """
        tab = self._cntwidget(count)
        if tab is None:
            return

        try:
            if pdf:
                tab.printing.check_pdf_support()
            else:
                tab.printing.check_printer_support()
        except browsertab.WebTabError as e:
            raise cmdexc.CommandError(e)

        if preview:
            diag = QPrintPreviewDialog()
            diag.setAttribute(Qt.WA_DeleteOnClose)
            diag.setWindowFlags(diag.windowFlags() |
                                Qt.WindowMaximizeButtonHint |
                                Qt.WindowMinimizeButtonHint)
            diag.paintRequested.connect(tab.printing.to_printer)
            diag.exec_()
        elif pdf:
            pdf = os.path.expanduser(pdf)
            directory = os.path.dirname(pdf)
            if directory and not os.path.exists(directory):
                os.mkdir(directory)
            tab.printing.to_pdf(pdf)
            log.misc.debug("Print to file: {}".format(pdf))
        else:
            diag = QPrintDialog()
            diag.setAttribute(Qt.WA_DeleteOnClose)
            diag.open(lambda: tab.printing.to_printer(diag.printer()))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_clone(self, bg=False, window=False):
        """Duplicate the current tab.

        Args:
            bg: Open in a background tab.
            window: Open in a new window.

        Return:
            The new QWebView.
        """
        cmdutils.check_exclusive((bg, window), 'bw')
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
        if config.get('tabs', 'show-favicons'):
            new_tabbed_browser.setTabIcon(idx, curtab.icon())
            if config.get('tabs', 'tabs-are-windows'):
                new_tabbed_browser.window().setWindowIcon(curtab.icon())
        newtab.data.keep_icon = True
        newtab.zoom.set_factor(curtab.zoom.factor())
        newtab.history.deserialize(curtab.history.serialize())
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
        history = self._current_widget().history
        # Catch common cases before e.g. cloning tab
        if not forward and not history.can_go_back():
            raise cmdexc.CommandError("At beginning of history.")
        elif forward and not history.can_go_forward():
            raise cmdexc.CommandError("At end of history.")

        if tab or bg or window:
            widget = self.tab_clone(bg, window)
        else:
            widget = self._current_widget()

        for _ in range(count):
            if forward:
                if not widget.history.can_go_forward():
                    raise cmdexc.CommandError("At end of history.")
                widget.history.forward()
            else:
                if not widget.history.can_go_back():
                    raise cmdexc.CommandError("At beginning of history.")
                widget.history.back()

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
    def back(self, tab=False, bg=False, window=False, count=1):
        """Go back in the history of the current tab.

        Args:
            tab: Go back in a new tab.
            bg: Go back in a background tab.
            window: Go back in a new window.
            count: How many pages to go back.
        """
        self._back_forward(tab, bg, window, count, forward=False)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
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
        segments = set(config.get('general', 'url-incdec-segments'))
        try:
            new_url = urlutils.incdec_number(url, incdec, segments=segments)
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

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       backend=usertypes.Backend.QtWebKit)
    @cmdutils.argument('where', choices=['prev', 'next', 'up', 'increment',
                                         'decrement'])
    def navigate(self, where: str, tab=False, bg=False, window=False):
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
        # save the pre-jump position in the special ' mark
        self.set_mark("'")

        cmdutils.check_exclusive((tab, bg, window), 'tbw')
        widget = self._current_widget()
        url = self._current_url().adjusted(QUrl.RemoveFragment)

        if where in ['prev', 'next']:
            # FIXME:qtwebengine have a proper API for this
            if widget.backend == usertypes.Backend.QtWebEngine:
                raise cmdexc.CommandError(":navigate prev/next is not "
                                          "supported yet with QtWebEngine")
            page = widget._widget.page()  # pylint: disable=protected-access
            frame = page.currentFrame()
            if frame is None:
                raise cmdexc.CommandError("No frame focused!")
        else:
            frame = None

        hintmanager = objreg.get('hintmanager', scope='tab', tab='current')
        if where == 'prev':
            assert frame is not None
            hintmanager.follow_prevnext(frame, url, prev=True, tab=tab,
                                        background=bg, window=window)
        elif where == 'next':
            assert frame is not None
            hintmanager.follow_prevnext(frame, url, prev=False, tab=tab,
                                        background=bg, window=window)
        elif where == 'up':
            self._navigate_up(url, tab, bg, window)
        elif where in ['decrement', 'increment']:
            self._navigate_incdec(url, where, tab, bg, window)
        else:  # pragma: no cover
            raise ValueError("Got called with invalid value {} for "
                             "`where'.".format(where))

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    @cmdutils.argument('count', count=True)
    def scroll_px(self, dx: int, dy: int, count=1):
        """Scroll the current tab by 'count * dx/dy' pixels.

        Args:
            dx: How much to scroll in x-direction.
            dy: How much to scroll in y-direction.
            count: multiplier
        """
        dx *= count
        dy *= count
        cmdutils.check_overflow(dx, 'int')
        cmdutils.check_overflow(dy, 'int')
        self._current_widget().scroller.delta(dx, dy)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    @cmdutils.argument('count', count=True)
    def scroll(self, direction: typing.Union[str, int], count=1):
        """Scroll the current tab in the given direction.

        Args:
            direction: In which direction to scroll
                       (up/down/left/right/top/bottom).
            count: multiplier
        """
        tab = self._current_widget()
        funcs = {
            'up': tab.scroller.up,
            'down': tab.scroller.down,
            'left': tab.scroller.left,
            'right': tab.scroller.right,
            'top': tab.scroller.top,
            'bottom': tab.scroller.bottom,
            'page-up': tab.scroller.page_up,
            'page-down': tab.scroller.page_down,
        }
        try:
            func = funcs[direction]
        except KeyError:
            expected_values = ', '.join(sorted(funcs))
            raise cmdexc.CommandError("Invalid value {!r} for direction - "
                                      "expected one of: {}".format(
                                          direction, expected_values))

        if direction in ['top', 'bottom']:
            func()
        else:
            func(count=count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    @cmdutils.argument('count', count=True)
    @cmdutils.argument('horizontal', flag='x')
    def scroll_perc(self, perc: float=None, horizontal=False, count=None):
        """Scroll to a specific percentage of the page.

        The percentage can be given either as argument or as count.
        If no percentage is given, the page is scrolled to the end.

        Args:
            perc: Percentage to scroll.
            horizontal: Scroll horizontally instead of vertically.
            count: Percentage to scroll.
        """
        # save the pre-jump position in the special ' mark
        self.set_mark("'")

        if perc is None and count is None:
            perc = 100
        elif count is not None:
            perc = count

        if horizontal:
            x = perc
            y = None
        else:
            x = None
            y = perc

        self._current_widget().scroller.to_perc(x, y)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    @cmdutils.argument('count', count=True)
    @cmdutils.argument('top_navigate', metavar='ACTION',
                       choices=('prev', 'decrement'))
    @cmdutils.argument('bottom_navigate', metavar='ACTION',
                       choices=('next', 'increment'))
    def scroll_page(self, x: float, y: float, *,
                    top_navigate: str=None, bottom_navigate: str=None,
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
        tab = self._current_widget()
        if not tab.url().isValid():
            # See https://github.com/The-Compiler/qutebrowser/issues/701
            return

        if bottom_navigate is not None and tab.scroller.at_bottom():
            self.navigate(bottom_navigate)
            return
        elif top_navigate is not None and tab.scroller.at_top():
            self.navigate(top_navigate)
            return

        try:
            tab.scroller.delta_page(count * x, count * y)
        except OverflowError:
            raise cmdexc.CommandError(
                "Numeric argument is too large for internal int "
                "representation.")

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def yank(self, title=False, sel=False, domain=False, pretty=False):
        """Yank the current URL/title to the clipboard or primary selection.

        Args:
            sel: Use the primary selection instead of the clipboard.
            title: Yank the title instead of the URL.
            domain: Yank only the scheme, domain, and port number.
            pretty: Yank the URL in pretty decoded form.
        """
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
            flags = QUrl.RemovePassword
            if not pretty:
                flags |= QUrl.FullyEncoded
            s = self._current_url().toString(flags)
            what = 'URL'

        if sel and utils.supports_selection():
            target = "primary selection"
        else:
            sel = False
            target = "clipboard"

        utils.set_clipboard(s, selection=sel)
        message.info(self._win_id, "Yanked {} to {}: {}".format(
                     what, target, s))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
    def zoom_in(self, count=1):
        """Increase the zoom level for the current tab.

        Args:
            count: How many steps to zoom in.
        """
        tab = self._current_widget()
        try:
            perc = tab.zoom.offset(count)
        except ValueError as e:
            raise cmdexc.CommandError(e)
        message.info(self._win_id, "Zoom level: {}%".format(perc))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
    def zoom_out(self, count=1):
        """Decrease the zoom level for the current tab.

        Args:
            count: How many steps to zoom out.
        """
        tab = self._current_widget()
        try:
            perc = tab.zoom.offset(-count)
        except ValueError as e:
            raise cmdexc.CommandError(e)
        message.info(self._win_id, "Zoom level: {}%".format(perc))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
    def zoom(self, zoom: int=None, count=None):
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
            tab.zoom.set_factor(float(level) / 100)
        except ValueError:
            raise cmdexc.CommandError("Can't zoom {}%!".format(level))
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

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
    def tab_prev(self, count=1):
        """Switch to the previous tab, or switch [count] tabs back.

        Args:
            count: How many tabs to switch back.
        """
        if self._count() == 0:
            # Running :tab-prev after last tab was closed
            # See https://github.com/The-Compiler/qutebrowser/issues/1448
            return
        newidx = self._current_index() - count
        if newidx >= 0:
            self._set_current_index(newidx)
        elif config.get('tabs', 'wrap'):
            self._set_current_index(newidx % self._count())
        else:
            raise cmdexc.CommandError("First tab")

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', count=True)
    def tab_next(self, count=1):
        """Switch to the next tab, or switch [count] tabs forward.

        Args:
            count: How many tabs to switch forward.
        """
        if self._count() == 0:
            # Running :tab-next after last tab was closed
            # See https://github.com/The-Compiler/qutebrowser/issues/1448
            return
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

        If the pasted text contains newlines, each line gets opened in its own
        tab.

        Args:
            sel: Use the primary selection instead of the clipboard.
            tab: Open in a new tab.
            bg: Open in a background tab.
            window: Open in new window.
        """
        force_search = False
        if sel and utils.supports_selection():
            target = "Primary selection"
        else:
            sel = False
            target = "Clipboard"
        text = utils.get_clipboard(selection=sel)
        if not text.strip():
            raise cmdexc.CommandError("{} is empty.".format(target))
        log.misc.debug("{} contained: {!r}".format(target, text))
        text_urls = [u for u in text.split('\n') if u.strip()]
        if (len(text_urls) > 1 and not urlutils.is_url(text_urls[0]) and
            urlutils.get_path_if_valid(
                text_urls[0], check_exists=True) is None):
            force_search = True
            text_urls = [text]
        for i, text_url in enumerate(text_urls):
            if not window and i > 0:
                tab = False
                bg = True
            try:
                url = urlutils.fuzzy_url(text_url, force_search=force_search)
            except urlutils.InvalidUrlError as e:
                raise cmdexc.CommandError(e)
            self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('index', completion=usertypes.Completion.tab)
    def buffer(self, index):
        """Select tab by index or url/title best match.

        Focuses window if necessary.

        Args:
            index: The [win_id/]index of the tab to focus. Or a substring
                   in which case the closest match will be focused.
        """
        index_parts = index.split('/', 1)

        try:
            for part in index_parts:
                int(part)
        except ValueError:
            model = instances.get(usertypes.Completion.tab)
            sf = sortfilter.CompletionFilterModel(source=model)
            sf.set_pattern(index)
            if sf.count() > 0:
                index = sf.data(sf.first_item())
                index_parts = index.split('/', 1)
            else:
                raise cmdexc.CommandError(
                    "No matching tab for: {}".format(index))

        if len(index_parts) == 2:
            win_id = int(index_parts[0])
            idx = int(index_parts[1])
        elif len(index_parts) == 1:
            idx = int(index_parts[0])
            active_win = objreg.get('app').activeWindow()
            if active_win is None:
                # Not sure how you enter a command without an active window...
                raise cmdexc.CommandError(
                    "No window specified and couldn't find active window!")
            win_id = active_win.win_id

        if win_id not in objreg.window_registry:
            raise cmdexc.CommandError(
                "There's no window with id {}!".format(win_id))

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)
        if not 0 < idx <= tabbed_browser.count():
            raise cmdexc.CommandError(
                "There's no tab with index {}!".format(idx))

        window = objreg.window_registry[win_id]
        window.activateWindow()
        window.raise_()
        tabbed_browser.setCurrentIndex(idx-1)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('index', choices=['last'])
    @cmdutils.argument('count', count=True)
    def tab_focus(self, index: typing.Union[str, int]=None, count=None):
        """Select the tab given as argument/[count].

        If neither count nor index are given, it behaves like tab-next.

        Args:
            index: The tab index to focus, starting with 1. The special value
                   `last` focuses the last focused tab. Negative indexes
                   counts from the end, such that -1 is the last tab.
            count: The tab index to focus, starting with 1.
        """
        if index == 'last':
            self._tab_focus_last()
            return
        if index is None and count is None:
            self.tab_next()
            return
        if index is not None and index < 0:
            index = self._count() + index + 1
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

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('direction', choices=['+', '-'])
    @cmdutils.argument('count', count=True)
    def tab_move(self, direction: str=None, count=None):
        """Move the current tab.

        Args:
            direction: `+` or `-` for relative moving, not given for absolute
                       moving.
            count: If moving absolutely: New position (default: 0)
                   If moving relatively: Offset.
        """
        if direction is None:
            # absolute moving
            new_idx = 0 if count is None else count - 1
        elif direction in '+-':
            # relative moving
            delta = 1 if count is None else count
            if direction == '-':
                new_idx = self._current_index() - delta
            elif direction == '+':  # pragma: no branch
                new_idx = self._current_index() + delta

            if config.get('tabs', 'wrap'):
                new_idx %= self._count()
        else:  # pragma: no cover
            raise ValueError("Invalid direction '{}'!".format(direction))

        if not 0 <= new_idx < self._count():
            raise cmdexc.CommandError("Can't move tab to position {}!".format(
                new_idx + 1))

        tab = self._current_widget()
        cur_idx = self._current_index()
        icon = self._tabbed_browser.tabIcon(cur_idx)
        label = self._tabbed_browser.page_title(cur_idx)
        cmdutils.check_overflow(cur_idx, 'int')
        cmdutils.check_overflow(new_idx, 'int')
        self._tabbed_browser.setUpdatesEnabled(False)
        try:
            color = self._tabbed_browser.tabBar().tab_data(
                cur_idx, 'indicator-color')
            self._tabbed_browser.removeTab(cur_idx)
            self._tabbed_browser.insertTab(new_idx, tab, icon, label)
            self._set_current_index(new_idx)
            self._tabbed_browser.set_tab_indicator_color(new_idx, color)
        finally:
            self._tabbed_browser.setUpdatesEnabled(True)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    def spawn(self, cmdline, userscript=False, verbose=False, detach=False):
        """Spawn a command in a shell.

        Note the `{url}` and `{url:pretty}` variables might be useful here.
        `{url}` gets replaced by the URL in fully encoded format and
        `{url:pretty}` uses a "pretty form" with most percent-encoded
        characters decoded.

        Args:
            userscript: Run the command as a userscript. You can use an
                        absolute path, or store the userscript in one of those
                        locations:
                            - `~/.local/share/qutebrowser/userscripts`
                              (or `$XDG_DATA_DIR`)
                            - `/usr/share/qutebrowser/userscripts`
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
            self._run_userscript(cmd, *args, verbose=verbose)
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

    def _run_userscript(self, cmd, *args, verbose=False):
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

        tab = self._tabbed_browser.currentWidget()
        if tab is not None and tab.caret.has_selection():
            env['QUTE_SELECTED_TEXT'] = tab.caret.selection()
            env['QUTE_SELECTED_HTML'] = tab.caret.selection(html=True)

        # FIXME:qtwebengine: If tab is None, run_async will fail!

        try:
            url = self._tabbed_browser.current_url()
        except qtutils.QtValueError:
            pass
        else:
            env['QUTE_URL'] = url.toString(QUrl.FullyEncoded)

        try:
            userscripts.run_async(tab, cmd, *args, win_id=self._win_id,
                                  env=env, verbose=verbose)
        except userscripts.UnsupportedError as e:
            raise cmdexc.CommandError(e)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def quickmark_save(self):
        """Save the current page as a quickmark."""
        quickmark_manager = objreg.get('quickmark-manager')
        quickmark_manager.prompt_save(self._win_id, self._current_url())

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('name',
                       completion=usertypes.Completion.quickmark_by_name)
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

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('name',
                       completion=usertypes.Completion.quickmark_by_name)
    def quickmark_del(self, name=None):
        """Delete a quickmark.

        Args:
            name: The name of the quickmark to delete. If not given, delete the
                  quickmark for the current page (choosing one arbitrarily
                  if there are more than one).
        """
        quickmark_manager = objreg.get('quickmark-manager')
        if name is None:
            url = self._current_url()
            try:
                name = quickmark_manager.get_by_qurl(url)
            except urlmarks.DoesNotExistError as e:
                raise cmdexc.CommandError(str(e))
        try:
            quickmark_manager.delete(name)
        except KeyError:
            raise cmdexc.CommandError("Quickmark '{}' not found!".format(name))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def bookmark_add(self, url=None, title=None, toggle=False):
        """Save the current page as a bookmark, or a specific url.

        If no url and title are provided, then save the current page as a
        bookmark.
        If a url and title have been provided, then save the given url as
        a bookmark with the provided title.

        You can view all saved bookmarks on the
        link:qute://bookmarks[bookmarks page].

        Args:
            url: url to save as a bookmark. If None, use url of current page.
            title: title of the new bookmark.
            toggle: remove the bookmark instead of raising an error if it
                    already exists.
        """
        if url and not title:
            raise cmdexc.CommandError('Title must be provided if url has '
                                      'been provided')
        bookmark_manager = objreg.get('bookmark-manager')
        if url is None:
            url = self._current_url()
        else:
            try:
                url = urlutils.fuzzy_url(url)
            except urlutils.InvalidUrlError as e:
                raise cmdexc.CommandError(e)
        if not title:
            title = self._current_title()
        try:
            was_added = bookmark_manager.add(url, title, toggle=toggle)
        except urlmarks.Error as e:
            raise cmdexc.CommandError(str(e))
        else:
            msg = "Bookmarked {}!" if was_added else "Removed bookmark {}!"
            message.info(self._win_id,
                         msg.format(url.toDisplayString()))

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('url', completion=usertypes.Completion.bookmark_by_url)
    def bookmark_load(self, url, tab=False, bg=False, window=False,
                      delete=False):
        """Load a bookmark.

        Args:
            url: The url of the bookmark to load.
            tab: Load the bookmark in a new tab.
            bg: Load the bookmark in a new background tab.
            window: Load the bookmark in a new window.
            delete: Whether to delete the bookmark afterwards.
        """
        try:
            qurl = urlutils.fuzzy_url(url)
        except urlutils.InvalidUrlError as e:
            raise cmdexc.CommandError(e)
        self._open(qurl, tab, bg, window)
        if delete:
            self.bookmark_del(url)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('url', completion=usertypes.Completion.bookmark_by_url)
    def bookmark_del(self, url=None):
        """Delete a bookmark.

        Args:
            url: The url of the bookmark to delete. If not given, use the
                 current page's url.
        """
        if url is None:
            url = self._current_url().toString(QUrl.RemovePassword
                                             | QUrl.FullyEncoded)
        try:
            objreg.get('bookmark-manager').delete(url)
        except KeyError:
            raise cmdexc.CommandError("Bookmark '{}' not found!".format(url))


    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    def follow_selected(self, *, tab=False):
        """Follow the selected text.

        Args:
            tab: Load the selected link in a new tab.
        """
        try:
            self._current_widget().caret.follow_selected(tab=tab)
        except browsertab.WebTabError as e:
            raise cmdexc.CommandError(str(e))

    @cmdutils.register(instance='command-dispatcher', name='inspector',
                       scope='window', backend=usertypes.Backend.QtWebKit)
    def toggle_inspector(self):
        """Toggle the web inspector.

        Note: Due a bug in Qt, the inspector will show incorrect request
        headers in the network tab.
        """
        tab = self._current_widget()
        if tab.data.inspector is None:
            if not config.get('general', 'developer-extras'):
                raise cmdexc.CommandError(
                    "Please enable developer-extras before using the "
                    "webinspector!")
            tab.data.inspector = inspector.WebInspector()
            # FIXME:qtwebengine have a proper API for this
            page = tab._widget.page()  # pylint: disable=protected-access
            tab.data.inspector.setPage(page)
            tab.data.inspector.show()
        elif tab.data.inspector.isVisible():
            tab.data.inspector.hide()
        else:
            if not config.get('general', 'developer-extras'):
                raise cmdexc.CommandError(
                    "Please enable developer-extras before using the "
                    "webinspector!")
            else:
                tab.data.inspector.show()

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       backend=usertypes.Backend.QtWebKit)
    @cmdutils.argument('dest_old', hide=True)
    def download(self, url=None, dest_old=None, *, mhtml_=False, dest=None):
        """Download a given URL, or current page if no URL given.

        The form `:download [url] [dest]` is deprecated, use `:download --dest
        [dest] [url]` instead.

        Args:
            url: The URL to download. If not given, download the current page.
            dest_old: (deprecated) Same as dest.
            dest: The file path to write the download to, or None to ask.
            mhtml_: Download the current page and all assets as mhtml file.
        """
        if dest_old is not None:
            message.warning(self._win_id,
                            ":download [url] [dest] is deprecated - use"
                            " download --dest [dest] [url]")
            if dest is not None:
                raise cmdexc.CommandError("Can't give two destinations for the"
                                          " download.")
            dest = dest_old

        download_manager = objreg.get('download-manager', scope='window',
                                      window=self._win_id)
        if url:
            if mhtml_:
                raise cmdexc.CommandError("Can only download the current page"
                                          " as mhtml.")
            url = urlutils.qurl_from_user_input(url)
            urlutils.raise_cmdexc_if_invalid(url)
            if dest is None:
                target = None
            else:
                target = usertypes.FileDownloadTarget(dest)
            download_manager.get(url, target=target)
        elif mhtml_:
            self._download_mhtml(dest)
        else:
            # FIXME:qtwebengine have a proper API for this
            tab = self._current_widget()
            page = tab._widget.page()  # pylint: disable=protected-access
            if dest is None:
                target = None
            else:
                target = usertypes.FileDownloadTarget(dest)
            download_manager.get(self._current_url(), page=page,
                                 target=target)

    def _download_mhtml(self, dest=None):
        """Download the current page as an MHTML file, including all assets.

        Args:
            dest: The file path to write the download to.
        """
        tab = self._current_widget()
        if dest is None:
            suggested_fn = self._current_title() + ".mht"
            suggested_fn = utils.sanitize_filename(suggested_fn)
            filename, q = downloads.ask_for_filename(
                suggested_fn, self._win_id, parent=tab,
            )
            if filename is not None:
                mhtml.start_download_checked(filename, tab=tab)
            else:
                q.answered.connect(functools.partial(
                    mhtml.start_download_checked, tab=tab))
                q.ask()
        else:
            mhtml.start_download_checked(dest, tab=tab)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def view_source(self):
        """Show the source of the current page."""
        # pylint: disable=no-member
        # WORKAROUND for https://bitbucket.org/logilab/pylint/issue/491/
        tab = self._current_widget()
        if tab.data.viewing_source:
            raise cmdexc.CommandError("Already viewing source!")

        def show_source_cb(source):
            """Show source as soon as it's ready."""
            lexer = pygments.lexers.HtmlLexer()
            formatter = pygments.formatters.HtmlFormatter(full=True,
                                                          linenos='table')
            highlighted = pygments.highlight(source, lexer, formatter)
            current_url = self._current_url()
            new_tab = self._tabbed_browser.tabopen(explicit=True)
            new_tab.set_html(highlighted, current_url)
            new_tab.data.viewing_source = True

        tab.dump_async(show_source_cb)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       debug=True)
    def debug_dump_page(self, dest, plain=False):
        """Dump the current page's content to a file.

        Args:
            dest: Where to write the file to.
            plain: Write plain text instead of HTML.
        """
        tab = self._current_widget()
        dest = os.path.expanduser(dest)

        def callback(data):
            try:
                with open(dest, 'w', encoding='utf-8') as f:
                    f.write(data)
            except OSError as e:
                message.error(self._win_id,
                              'Could not write page: {}'.format(e))
            else:
                message.info(self._win_id, "Dumped page to {}.".format(dest))

        tab.dump_async(callback, plain=plain)

    @cmdutils.register(instance='command-dispatcher', name='help',
                       scope='window')
    @cmdutils.argument('topic', completion=usertypes.Completion.helptopic)
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

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def messages(self, level='error', plain=False, tab=False, bg=False,
                 window=False):
        """Show a log of past messages.

        Args:
            level: Include messages with `level` or higher severity.
                   Valid values: vdebug, debug, info, warning, error, critical.
            plain: Whether to show plaintext (as opposed to html).
            tab: Open in a new tab.
            bg: Open in a background tab.
            window: Open in a new window.
        """
        if level.upper() not in log.LOG_LEVELS:
            raise cmdexc.CommandError("Invalid log level {}!".format(level))
        if plain:
            url = QUrl('qute://plainlog?level={}'.format(level))
        else:
            url = QUrl('qute://log?level={}'.format(level))
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher',
                       modes=[KeyMode.insert], hide=True, scope='window',
                       backend=usertypes.Backend.QtWebKit)
    def open_editor(self):
        """Open an external editor with the currently selected form field.

        The editor which should be launched can be configured via the
        `general -> editor` config option.
        """
        # FIXME:qtwebengine have a proper API for this
        tab = self._current_widget()
        page = tab._widget.page()  # pylint: disable=protected-access
        try:
            elem = webelem.focus_elem(page.currentFrame())
        except webelem.IsNullError:
            raise cmdexc.CommandError("No element focused!")
        if not elem.is_editable(strict=True):
            raise cmdexc.CommandError("Focused element is not editable!")
        if elem.is_content_editable():
            text = str(elem)
        else:
            text = elem.evaluateJavaScript('this.value')
        ed = editor.ExternalEditor(self._win_id, self._tabbed_browser)
        ed.editing_finished.connect(functools.partial(
            self.on_editing_finished, elem))
        ed.edit(text)

    def on_editing_finished(self, elem, text):
        """Write the editor text into the form field and clean up tempfile.

        Callback for GUIProcess when the editor was closed.

        Args:
            elem: The WebElementWrapper which was modified.
            text: The new text to insert.
        """
        try:
            elem.set_text(text)
        except webelem.IsNullError:
            raise cmdexc.CommandError("Element vanished while editing!")

    @cmdutils.register(instance='command-dispatcher',
                       modes=[KeyMode.insert], hide=True, scope='window',
                       needs_js=True, backend=usertypes.Backend.QtWebKit)
    def paste_primary(self):
        """Paste the primary selection at cursor position."""
        # FIXME:qtwebengine have a proper API for this
        tab = self._current_widget()
        page = tab._widget.page()  # pylint: disable=protected-access
        try:
            elem = webelem.focus_elem(page.currentFrame())
        except webelem.IsNullError:
            raise cmdexc.CommandError("No element focused!")
        if not elem.is_editable(strict=True):
            raise cmdexc.CommandError("Focused element is not editable!")

        try:
            sel = utils.get_clipboard(selection=True)
        except utils.SelectionUnsupportedError:
            sel = utils.get_clipboard()

        log.misc.debug("Pasting primary selection into element {}".format(
            elem.debug_text()))
        elem.evaluateJavaScript("""
            var sel = '{}';
            var event = document.createEvent('TextEvent');
            event.initTextEvent('textInput', true, true, null, sel);
            this.dispatchEvent(event);
        """.format(webelem.javascript_escape(sel)))

    def _search_cb(self, found, *, tab, old_scroll_pos, options, text, prev):
        """Callback called from search/search_next/search_prev.

        Args:
            found: Whether the text was found.
            tab: The AbstractTab in which the search was made.
            old_scroll_pos: The scroll position (QPoint) before the search.
            options: The options (dict) the search was made with.
            text: The text searched for.
            prev: Whether we're searching backwards (i.e. :search-prev)
        """
        # :search/:search-next without reverse -> down
        # :search/:search-next    with reverse -> up
        # :search-prev         without reverse -> up
        # :search-prev            with reverse -> down
        going_up = options['reverse'] ^ prev

        if found:
            # Check if the scroll position got smaller and show info.
            if not going_up and tab.scroller.pos_px().y() < old_scroll_pos.y():
                message.info(self._win_id, "Search hit BOTTOM, continuing "
                             "at TOP", immediately=True)
            elif going_up and tab.scroller.pos_px().y() > old_scroll_pos.y():
                message.info(self._win_id, "Search hit TOP, continuing at "
                             "BOTTOM", immediately=True)
        else:
            message.warning(self._win_id, "Text '{}' not found on "
                            "page!".format(text), immediately=True)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    def search(self, text="", reverse=False):
        """Search for a text on the current page. With no text, clear results.

        Args:
            text: The text to search for.
            reverse: Reverse search direction.
        """
        self.set_mark("'")
        tab = self._current_widget()
        tab.search.clear()

        options = {
            'ignore_case': config.get('general', 'ignore-case'),
            'reverse': reverse,
        }
        self._tabbed_browser.search_text = text
        self._tabbed_browser.search_options = dict(options)

        if text:
            cb = functools.partial(self._search_cb, tab=tab,
                                   old_scroll_pos=tab.scroller.pos_px(),
                                   options=options, text=text, prev=False)
        else:
            cb = None

        options['result_cb'] = cb
        tab.search.search(text, **options)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    @cmdutils.argument('count', count=True)
    def search_next(self, count=1):
        """Continue the search to the ([count]th) next term.

        Args:
            count: How many elements to ignore.
        """
        tab = self._current_widget()
        window_text = self._tabbed_browser.search_text
        window_options = self._tabbed_browser.search_options

        if window_text is None:
            raise cmdexc.CommandError("No search done yet.")

        self.set_mark("'")

        if window_text is not None and window_text != tab.search.text:
            tab.search.clear()
            tab.search.search(window_text, **window_options)
            count -= 1

        if count == 0:
            return

        cb = functools.partial(self._search_cb, tab=tab,
                               old_scroll_pos=tab.scroller.pos_px(),
                               options=window_options, text=window_text,
                               prev=False)

        for _ in range(count - 1):
            tab.search.next_result()
        tab.search.next_result(result_cb=cb)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    @cmdutils.argument('count', count=True)
    def search_prev(self, count=1):
        """Continue the search to the ([count]th) previous term.

        Args:
            count: How many elements to ignore.
        """
        tab = self._current_widget()
        window_text = self._tabbed_browser.search_text
        window_options = self._tabbed_browser.search_options

        if window_text is None:
            raise cmdexc.CommandError("No search done yet.")

        self.set_mark("'")

        if window_text is not None and window_text != tab.search.text:
            tab.search.clear()
            tab.search.search(window_text, **window_options)
            count -= 1

        if count == 0:
            return

        cb = functools.partial(self._search_cb, tab=tab,
                               old_scroll_pos=tab.scroller.pos_px(),
                               options=window_options, text=window_text,
                               prev=True)

        for _ in range(count - 1):
            tab.search.prev_result()
        tab.search.prev_result(result_cb=cb)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_next_line(self, count=1):
        """Move the cursor or selection to the next line.

        Args:
            count: How many lines to move.
        """
        self._current_widget().caret.move_to_next_line(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_prev_line(self, count=1):
        """Move the cursor or selection to the prev line.

        Args:
            count: How many lines to move.
        """
        self._current_widget().caret.move_to_prev_line(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_next_char(self, count=1):
        """Move the cursor or selection to the next char.

        Args:
            count: How many lines to move.
        """
        self._current_widget().caret.move_to_next_char(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_prev_char(self, count=1):
        """Move the cursor or selection to the previous char.

        Args:
            count: How many chars to move.
        """
        self._current_widget().caret.move_to_prev_char(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_end_of_word(self, count=1):
        """Move the cursor or selection to the end of the word.

        Args:
            count: How many words to move.
        """
        self._current_widget().caret.move_to_end_of_word(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_next_word(self, count=1):
        """Move the cursor or selection to the next word.

        Args:
            count: How many words to move.
        """
        self._current_widget().caret.move_to_next_word(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_prev_word(self, count=1):
        """Move the cursor or selection to the previous word.

        Args:
            count: How many words to move.
        """
        self._current_widget().caret.move_to_prev_word(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def move_to_start_of_line(self):
        """Move the cursor or selection to the start of the line."""
        self._current_widget().caret.move_to_start_of_line()

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def move_to_end_of_line(self):
        """Move the cursor or selection to the end of line."""
        self._current_widget().caret.move_to_end_of_line()

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_start_of_next_block(self, count=1):
        """Move the cursor or selection to the start of next block.

        Args:
            count: How many blocks to move.
        """
        self._current_widget().caret.move_to_start_of_next_block(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_start_of_prev_block(self, count=1):
        """Move the cursor or selection to the start of previous block.

        Args:
            count: How many blocks to move.
        """
        self._current_widget().caret.move_to_start_of_prev_block(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_end_of_next_block(self, count=1):
        """Move the cursor or selection to the end of next block.

        Args:
            count: How many blocks to move.
        """
        self._current_widget().caret.move_to_end_of_next_block(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    @cmdutils.argument('count', count=True)
    def move_to_end_of_prev_block(self, count=1):
        """Move the cursor or selection to the end of previous block.

        Args:
            count: How many blocks to move.
        """
        self._current_widget().caret.move_to_end_of_prev_block(count)

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def move_to_start_of_document(self):
        """Move the cursor or selection to the start of the document."""
        self._current_widget().caret.move_to_start_of_document()

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def move_to_end_of_document(self):
        """Move the cursor or selection to the end of the document."""
        self._current_widget().caret.move_to_end_of_document()

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def yank_selected(self, sel=False, keep=False):
        """Yank the selected text to the clipboard or primary selection.

        Args:
            sel: Use the primary selection instead of the clipboard.
            keep: If given, stay in visual mode after yanking.
        """
        caret = self._current_widget().caret
        s = caret.selection()
        if not caret.has_selection() or len(s) == 0:
            message.info(self._win_id, "Nothing to yank")
            return

        if sel and utils.supports_selection():
            target = "primary selection"
        else:
            sel = False
            target = "clipboard"
        utils.set_clipboard(s, sel)
        message.info(self._win_id, "{} {} yanked to {}".format(
            len(s), "char" if len(s) == 1 else "chars", target))
        if not keep:
            modeman.maybe_leave(self._win_id, KeyMode.caret, "yank selected")

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def toggle_selection(self):
        """Toggle caret selection mode."""
        self._current_widget().caret.toggle_selection()

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       modes=[KeyMode.caret], scope='window')
    def drop_selection(self):
        """Drop selection and keep selection mode enabled."""
        self._current_widget().caret.drop_selection()

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       debug=True)
    @cmdutils.argument('count', count=True)
    def debug_webaction(self, action, count=1):
        """Execute a webaction.

        See http://doc.qt.io/qt-5/qwebpage.html#WebAction-enum for the
        available actions.

        Args:
            action: The action to execute, e.g. MoveToNextChar.
            count: How many times to repeat the action.
        """
        tab = self._current_widget()

        if tab.backend == usertypes.Backend.QtWebKit:
            assert QWebPage is not None
            member = getattr(QWebPage, action, None)
            base = QWebPage.WebAction
        elif tab.backend == usertypes.Backend.QtWebEngine:
            assert QWebEnginePage is not None
            member = getattr(QWebEnginePage, action, None)
            base = QWebEnginePage.WebAction

        if not isinstance(member, base):
            raise cmdexc.CommandError("{} is not a valid web action!".format(
                action))

        for _ in range(count):
            # This whole command is backend-specific anyways, so it makes no
            # sense to introduce some API for this.
            # pylint: disable=protected-access
            tab._widget.triggerPageAction(member)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0, no_cmd_split=True)
    def jseval(self, js_code, quiet=False):
        """Evaluate a JavaScript string.

        Args:
            js_code: The string to evaluate.
            quiet: Don't show resulting JS object.
        """
        if quiet:
            jseval_cb = None
        else:
            def jseval_cb(out):
                if out is None:
                    # Getting the actual error (if any) seems to be difficult.
                    # The error does end up in
                    # BrowserPage.javaScriptConsoleMessage(), but
                    # distinguishing between :jseval errors and errors from the
                    # webpage is not trivial...
                    message.info(self._win_id, 'No output or error')
                else:
                    # The output can be a string, number, dict, array, etc. But
                    # *don't* output too much data, as this will make
                    # qutebrowser hang
                    out = str(out)
                    if len(out) > 5000:
                        out = out[:5000] + ' [...trimmed...]'
                    message.info(self._win_id, out)

        self._current_widget().run_js_async(js_code, callback=jseval_cb)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def fake_key(self, keystring, global_=False):
        """Send a fake keypress or key string to the website or qutebrowser.

        :fake-key xy - sends the keychain 'xy'
        :fake-key <Ctrl-x> - sends Ctrl-x
        :fake-key <Escape> - sends the escape key

        Args:
            keystring: The keystring to send.
            global_: If given, the keys are sent to the qutebrowser UI.
        """
        try:
            keyinfos = utils.parse_keystring(keystring)
        except utils.KeyParseError as e:
            raise cmdexc.CommandError(str(e))

        for keyinfo in keyinfos:
            press_event = QKeyEvent(QEvent.KeyPress, keyinfo.key,
                                    keyinfo.modifiers, keyinfo.text)
            release_event = QKeyEvent(QEvent.KeyRelease, keyinfo.key,
                                      keyinfo.modifiers, keyinfo.text)

            if global_:
                receiver = QApplication.focusWindow()
                if receiver is None:
                    raise cmdexc.CommandError("No focused window!")
            else:
                try:
                    tab = objreg.get('tab', scope='tab', tab='current')
                except objreg.RegistryUnavailableError:
                    raise cmdexc.CommandError("No focused webview!")
                # pylint: disable=protected-access
                receiver = tab._widget
                # pylint: enable=protected-access

            QApplication.postEvent(receiver, press_event)
            QApplication.postEvent(receiver, release_event)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       debug=True)
    def debug_clear_ssl_errors(self):
        """Clear remembered SSL error answers."""
        self._current_widget().clear_ssl_errors()

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def edit_url(self, url=None, bg=False, tab=False, window=False):
        """Navigate to a url formed in an external editor.

        The editor which should be launched can be configured via the
        `general -> editor` config option.

        Args:
            url: URL to edit; defaults to the current page url.
            bg: Open in a new background tab.
            tab: Open in a new tab.
            window: Open in a new window.
        """
        cmdutils.check_exclusive((tab, bg, window), 'tbw')

        old_url = self._current_url().toString()

        ed = editor.ExternalEditor(self._win_id, self._tabbed_browser)

        # Passthrough for openurl args (e.g. -t, -b, -w)
        ed.editing_finished.connect(functools.partial(
            self._open_if_changed, old_url=old_url, bg=bg, tab=tab,
            window=window))

        ed.edit(url or old_url)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def set_mark(self, key):
        """Set a mark at the current scroll position in the current tab.

        Args:
            key: mark identifier; capital indicates a global mark
        """
        self._tabbed_browser.set_mark(key)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def jump_mark(self, key):
        """Jump to the mark named by `key`.

        Args:
            key: mark identifier; capital indicates a global mark
        """
        self._tabbed_browser.jump_mark(key)

    def _open_if_changed(self, url=None, old_url=None, bg=False, tab=False,
                         window=False):
        """Open a URL unless it's already open in the tab.

        Args:
            old_url: The original URL to compare against.
            url: The URL to open.
            bg: Open in a new background tab.
            tab: Open in a new tab.
            window: Open in a new window.
        """
        if bg or tab or window or url != old_url:
            self.openurl(url=url, bg=bg, tab=tab, window=window)
