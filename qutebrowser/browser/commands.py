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

"""Command dispatcher for TabbedBrowser."""

import os.path
import shlex
import functools
import typing

from PyQt5.QtWidgets import QApplication, QTabBar
from PyQt5.QtCore import pyqtSlot, Qt, QUrl, QEvent, QUrlQuery

from qutebrowser.commands import userscripts, runners
from qutebrowser.api import cmdutils
from qutebrowser.config import config, configdata
from qutebrowser.browser import (urlmarks, browsertab, inspector, navigate,
                                 webelem, downloads)
from qutebrowser.keyinput import modeman, keyutils
from qutebrowser.utils import (message, usertypes, log, qtutils, urlutils,
                               objreg, utils, standarddir, debug)
from qutebrowser.utils.usertypes import KeyMode
from qutebrowser.misc import editor, guiprocess, objects
from qutebrowser.completion.models import urlmodel, miscmodels
from qutebrowser.mainwindow import mainwindow


class CommandDispatcher:

    """Command dispatcher for TabbedBrowser.

    Contains all commands which are related to the current tab.

    We can't simply add these commands to BrowserTab directly and use
    currentWidget() for TabbedBrowser.cmd because at the time
    cmdutils.register() decorators are run, currentWidget() will return None.

    Attributes:
        _win_id: The window ID the CommandDispatcher is associated with.
        _tabbed_browser: The TabbedBrowser used.
    """

    def __init__(self, win_id, tabbed_browser):
        self._win_id = win_id
        self._tabbed_browser = tabbed_browser

    def __repr__(self):
        return utils.get_repr(self)

    def _new_tabbed_browser(self, private):
        """Get a tabbed-browser from a new window."""
        args = QApplication.instance().arguments()
        if private and '--single-process' in args:
            raise cmdutils.CommandError("Private windows are unavailable with "
                                        "the single-process process model.")

        new_window = mainwindow.MainWindow(private=private)
        new_window.show()
        return new_window.tabbed_browser

    def _count(self) -> int:
        """Convenience method to get the widget count."""
        return self._tabbed_browser.widget.count()

    def _set_current_index(self, idx):
        """Convenience method to set the current widget index."""
        cmdutils.check_overflow(idx, 'int')
        self._tabbed_browser.widget.setCurrentIndex(idx)

    def _current_index(self):
        """Convenience method to get the current widget index."""
        return self._tabbed_browser.widget.currentIndex()

    def _current_url(self):
        """Convenience method to get the current url."""
        try:
            return self._tabbed_browser.current_url()
        except qtutils.QtValueError as e:
            msg = "Current URL is invalid"
            if e.reason:
                msg += " ({})".format(e.reason)
            msg += "!"
            raise cmdutils.CommandError(msg)

    def _current_title(self):
        """Convenience method to get the current title."""
        return self._current_widget().title()

    def _current_widget(self):
        """Get the currently active widget from a command."""
        widget = self._tabbed_browser.widget.currentWidget()
        if widget is None:
            raise cmdutils.CommandError("No WebView available yet!")
        return widget

    def _open(self, url, tab=False, background=False, window=False,
              related=False, private=None):
        """Helper function to open a page.

        Args:
            url: The URL to open as QUrl.
            tab: Whether to open in a new tab.
            background: Whether to open in the background.
            window: Whether to open in a new window
            private: If opening a new window, open it in private browsing mode.
                     If not given, inherit the current window's mode.
        """
        urlutils.raise_cmdexc_if_invalid(url)
        tabbed_browser = self._tabbed_browser
        cmdutils.check_exclusive((tab, background, window, private), 'tbwp')
        if window and private is None:
            private = self._tabbed_browser.is_private

        if window or private:
            tabbed_browser = self._new_tabbed_browser(private)
            tabbed_browser.tabopen(url)
        elif tab:
            tabbed_browser.tabopen(url, background=False, related=related)
        elif background:
            tabbed_browser.tabopen(url, background=True, related=related)
        else:
            widget = self._current_widget()
            widget.load_url(url)

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
            return self._tabbed_browser.widget.currentWidget()
        elif 1 <= count <= self._count():
            cmdutils.check_overflow(count + 1, 'int')
            return self._tabbed_browser.widget.widget(count - 1)
        else:
            return None

    def _tab_focus_stack(self, mode: str, *, show_error: bool = True) -> None:
        """Select the tab which was last focused."""
        tab_deque = self._tabbed_browser.tab_deque
        cur_tab = self._cntwidget()

        try:
            if mode == "last":
                tab = tab_deque.last(cur_tab)
            elif mode == "stack-prev":
                tab = tab_deque.prev(cur_tab)
            elif mode == "stack-next":
                tab = tab_deque.next(cur_tab)
            else:
                raise NotImplementedError(
                    "Missing implementation for stack mode!")
        except IndexError:
            if not show_error:
                return
            raise cmdutils.CommandError("Could not find requested tab!")

        idx = self._tabbed_browser.widget.indexOf(tab)
        if idx == -1:
            raise cmdutils.CommandError("Requested tab vanished!")
        self._set_current_index(idx)

    def _get_selection_override(self, prev, next_, opposite):
        """Helper function for tab_close to get the tab to select.

        Args:
            prev: Force selecting the tab before the current tab.
            next_: Force selecting the tab after the current tab.
            opposite: Force selecting the tab in the opposite direction of
                      what's configured in 'tabs.select_on_remove'.

        Return:
            QTabBar.SelectLeftTab, QTabBar.SelectRightTab, or None if no change
            should be made.
        """
        cmdutils.check_exclusive((prev, next_, opposite), 'pno')
        if prev:
            return QTabBar.SelectLeftTab
        elif next_:
            return QTabBar.SelectRightTab
        elif opposite:
            conf_selection = config.val.tabs.select_on_remove
            if conf_selection == QTabBar.SelectLeftTab:
                return QTabBar.SelectRightTab
            elif conf_selection == QTabBar.SelectRightTab:
                return QTabBar.SelectLeftTab
            elif conf_selection == QTabBar.SelectPreviousTab:
                raise cmdutils.CommandError(
                    "-o is not supported with 'tabs.select_on_remove' set to "
                    "'last-used'!")
            else:  # pragma: no cover
                raise ValueError("Invalid select_on_remove value "
                                 "{!r}!".format(conf_selection))
        return None

    def _tab_close(self, tab, prev=False, next_=False, opposite=False):
        """Helper function for tab_close be able to handle message.async.

        Args:
            tab: Tab object to select be closed.
            prev: Force selecting the tab before the current tab.
            next_: Force selecting the tab after the current tab.
            opposite: Force selecting the tab in the opposite direction of
                      what's configured in 'tabs.select_on_remove'.
            count: The tab index to close, or None
        """
        tabbar = self._tabbed_browser.widget.tabBar()
        selection_override = self._get_selection_override(prev, next_,
                                                          opposite)

        if selection_override is None:
            self._tabbed_browser.close_tab(tab)
        else:
            old_selection_behavior = tabbar.selectionBehaviorOnRemove()
            tabbar.setSelectionBehaviorOnRemove(selection_override)
            self._tabbed_browser.close_tab(tab)
            tabbar.setSelectionBehaviorOnRemove(old_selection_behavior)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def tab_close(self, prev=False, next_=False, opposite=False,
                  force=False, count=None):
        """Close the current/[count]th tab.

        Args:
            prev: Force selecting the tab before the current tab.
            next_: Force selecting the tab after the current tab.
            opposite: Force selecting the tab in the opposite direction of
                      what's configured in 'tabs.select_on_remove'.
            force: Avoid confirmation for pinned tabs.
            count: The tab index to close, or None
        """
        tab = self._cntwidget(count)
        if tab is None:
            return
        close = functools.partial(self._tab_close, tab, prev,
                                  next_, opposite)

        self._tabbed_browser.tab_close_prompt_if_pinned(tab, force, close)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       name='tab-pin')
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def tab_pin(self, count=None):
        """Pin/Unpin the current/[count]th tab.

        Pinning a tab shrinks it to the size of its title text.
        Attempting to close a pinned tab will cause a confirmation,
        unless --force is passed.

        Args:
            count: The tab index to pin or unpin, or None
        """
        tab = self._cntwidget(count)
        if tab is None:
            return

        to_pin = not tab.data.pinned
        self._tabbed_browser.widget.set_tab_pinned(tab, to_pin)

    @cmdutils.register(instance='command-dispatcher', name='open',
                       maxsplit=0, scope='window')
    @cmdutils.argument('url', completion=urlmodel.url)
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def openurl(self, url=None, related=False,
                bg=False, tab=False, window=False, count=None, secure=False,
                private=False):
        """Open a URL in the current/[count]th tab.

        If the URL contains newlines, each line gets opened in its own tab.

        Args:
            url: The URL to open.
            bg: Open in a new background tab.
            tab: Open in a new tab.
            window: Open in a new window.
            related: If opening a new tab, position the tab as related to the
                     current one (like clicking on a link).
            count: The tab index to open the URL in, or None.
            secure: Force HTTPS.
            private: Open a new window in private browsing mode.
        """
        if url is None:
            urls = [config.val.url.default_page]
        else:
            urls = self._parse_url_input(url)

        for i, cur_url in enumerate(urls):
            if secure and cur_url.scheme() == 'http':
                cur_url.setScheme('https')

            if not window and i > 0:
                tab = False
                bg = True

            if tab or bg or window or private:
                self._open(cur_url, tab, bg, window, related=related,
                           private=private)
            else:
                curtab = self._cntwidget(count)
                if curtab is None:
                    if count is None:
                        # We want to open a URL in the current tab, but none
                        # exists yet.
                        self._tabbed_browser.tabopen(cur_url)
                    else:
                        # Explicit count with a tab that doesn't exist.
                        return
                elif curtab.navigation_blocked():
                    message.info("Tab is pinned!")
                else:
                    curtab.load_url(cur_url)

    def _parse_url(self, url, *, force_search=False):
        """Parse a URL or quickmark or search query.

        Args:
            url: The URL to parse.
            force_search: Whether to force a search even if the content can be
                          interpreted as a URL or a path.

        Return:
            A URL that can be opened.
        """
        try:
            return objreg.get('quickmark-manager').get(url)
        except urlmarks.Error:
            try:
                return urlutils.fuzzy_url(url, force_search=force_search)
            except urlutils.InvalidUrlError as e:
                # We don't use cmdutils.CommandError here as this can be
                # called async from edit_url
                message.error(str(e))
                return None

    def _parse_url_input(self, url):
        """Parse a URL or newline-separated list of URLs.

        Args:
            url: The URL or list to parse.

        Return:
            A list of URLs that can be opened.
        """
        if isinstance(url, QUrl):
            yield url
            return

        force_search = False
        urllist = [u for u in url.split('\n') if u.strip()]
        if (len(urllist) > 1 and not urlutils.is_url(urllist[0]) and
                urlutils.get_path_if_valid(urllist[0], check_exists=True)
                is None):
            urllist = [url]
            force_search = True
        for cur_url in urllist:
            parsed = self._parse_url(cur_url, force_search=force_search)
            if parsed is not None:
                yield parsed

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
        cur_title = self._tabbed_browser.widget.page_title(
            self._current_index())
        try:
            history = curtab.history.private_api.serialize()
        except browsertab.WebTabError as e:
            raise cmdutils.CommandError(e)

        # The new tab could be in a new tabbed_browser (e.g. because of
        # tabs.tabs_are_windows being set)
        if window:
            new_tabbed_browser = self._new_tabbed_browser(
                private=self._tabbed_browser.is_private)
        else:
            new_tabbed_browser = self._tabbed_browser
        newtab = new_tabbed_browser.tabopen(background=bg)
        new_tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=newtab.win_id)
        idx = new_tabbed_browser.widget.indexOf(newtab)

        new_tabbed_browser.widget.set_page_title(idx, cur_title)
        if curtab.data.should_show_icon():
            new_tabbed_browser.widget.setTabIcon(idx, curtab.icon())
            if config.val.tabs.tabs_are_windows:
                new_tabbed_browser.widget.window().setWindowIcon(curtab.icon())

        newtab.data.keep_icon = True
        newtab.history.private_api.deserialize(history)
        newtab.zoom.set_factor(curtab.zoom.factor())
        new_tabbed_browser.widget.set_tab_pinned(newtab, curtab.data.pinned)
        return newtab

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('index', completion=miscmodels.other_buffer)
    def tab_take(self, index, keep=False):
        """Take a tab from another window.

        Args:
            index: The [win_id/]index of the tab to take. Or a substring
                   in which case the closest match will be taken.
            keep: If given, keep the old tab around.
        """
        if config.val.tabs.tabs_are_windows:
            raise cmdutils.CommandError("Can't take tabs when using "
                                        "windows as tabs")

        tabbed_browser, tab = self._resolve_buffer_index(index)

        if tabbed_browser is self._tabbed_browser:
            raise cmdutils.CommandError("Can't take a tab from the same "
                                        "window")

        self._open(tab.url(), tab=True)
        if not keep:
            tabbed_browser.close_tab(tab, add_undo=False)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('win_id', completion=miscmodels.window)
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def tab_give(self, win_id: int = None, keep: bool = False,
                 count: int = None, private: bool = False) -> None:
        """Give the current tab to a new or existing window if win_id given.

        If no win_id is given, the tab will get detached into a new window.

        Args:
            win_id: The window ID of the window to give the current tab to.
            keep: If given, keep the old tab around.
            count: Overrides win_id (index starts at 1 for win_id=0).
            private: If the tab should be detached into a private instance.
        """
        if config.val.tabs.tabs_are_windows:
            raise cmdutils.CommandError("Can't give tabs when using "
                                        "windows as tabs")

        if count is not None:
            win_id = count - 1

        if win_id == self._win_id:
            raise cmdutils.CommandError("Can't give a tab to the same window")

        if win_id is None:
            if self._count() < 2 and not keep:
                raise cmdutils.CommandError("Cannot detach from a window with "
                                            "only one tab")

            tabbed_browser = self._new_tabbed_browser(
                private=private or self._tabbed_browser.is_private)
        else:
            if win_id not in objreg.window_registry:
                raise cmdutils.CommandError(
                    "There's no window with id {}!".format(win_id))

            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)

            if private and not tabbed_browser.is_private:
                raise cmdutils.CommandError(
                    "The window with id {} is not private".format(win_id))

        tabbed_browser.tabopen(self._current_url())
        if not keep:
            self._tabbed_browser.close_tab(self._current_widget(),
                                           add_undo=False)

    def _back_forward(self, tab, bg, window, count, forward):
        """Helper function for :back/:forward."""
        history = self._current_widget().history
        # Catch common cases before e.g. cloning tab
        if not forward and not history.can_go_back():
            raise cmdutils.CommandError("At beginning of history.")
        if forward and not history.can_go_forward():
            raise cmdutils.CommandError("At end of history.")

        if tab or bg or window:
            widget = self.tab_clone(bg, window)
        else:
            widget = self._current_widget()

        try:
            if forward:
                widget.history.forward(count)
            else:
                widget.history.back(count)
        except browsertab.WebTabError as e:
            raise cmdutils.CommandError(e)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', value=cmdutils.Value.count)
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
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def forward(self, tab=False, bg=False, window=False, count=1):
        """Go forward in the history of the current tab.

        Args:
            tab: Go forward in a new tab.
            bg: Go forward in a background tab.
            window: Go forward in a new window.
            count: How many pages to go forward.
        """
        self._back_forward(tab, bg, window, count, forward=True)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('where', choices=['prev', 'next', 'up', 'increment',
                                         'decrement'])
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def navigate(self, where: str, tab: bool = False, bg: bool = False,
                 window: bool = False, count: int = 1) -> None:
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
                  Uses the
                  link:settings{outsuffix}#url.incdec_segments[url.incdec_segments]
                  config option.
                - `decrement`: Decrement the last number in the URL.
                  Uses the
                  link:settings{outsuffix}#url.incdec_segments[url.incdec_segments]
                  config option.

            tab: Open in a new tab.
            bg: Open in a background tab.
            window: Open in a new window.
            count: For `increment` and `decrement`, the number to change the
                   URL by. For `up`, the number of levels to go up in the URL.
        """
        cmdutils.check_exclusive((tab, bg, window), 'tbw')
        widget = self._current_widget()
        url = self._current_url()

        handlers = {
            'prev': functools.partial(navigate.prevnext, prev=True),
            'next': functools.partial(navigate.prevnext, prev=False),
            'up': navigate.path_up,
            'decrement': functools.partial(navigate.incdec,
                                           inc_or_dec='decrement'),
            'increment': functools.partial(navigate.incdec,
                                           inc_or_dec='increment'),
        }  # type: typing.Dict[str, typing.Callable]

        try:
            if where in ['prev', 'next']:
                handler = handlers[where]
                handler(browsertab=widget, win_id=self._win_id, baseurl=url,
                        tab=tab, background=bg, window=window)
            elif where in ['up', 'increment', 'decrement']:
                if where == 'up':
                    url = url.adjusted(QUrl.RemoveFragment | QUrl.RemoveQuery)
                new_url = handlers[where](url, count)
                self._open(new_url, tab, bg, window, related=True)
            else:  # pragma: no cover
                raise ValueError("Got called with invalid value {} for "
                                 "`where'.".format(where))
        except navigate.Error as e:
            raise cmdutils.CommandError(e)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', value=cmdutils.Value.count)
    @cmdutils.argument('top_navigate', metavar='ACTION',
                       choices=('prev', 'decrement'))
    @cmdutils.argument('bottom_navigate', metavar='ACTION',
                       choices=('next', 'increment'))
    def scroll_page(self, x: float, y: float, *,
                    top_navigate: str = None, bottom_navigate: str = None,
                    count: int = 1) -> None:
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
            # See https://github.com/qutebrowser/qutebrowser/issues/701
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
            raise cmdutils.CommandError(
                "Numeric argument is too large for internal int "
                "representation.")

    def _yank_url(self, what):
        """Helper method for yank() to get the URL to copy."""
        assert what in ['url', 'pretty-url'], what

        if what == 'pretty-url':
            flags = QUrl.RemovePassword | QUrl.DecodeReserved
        else:
            flags = QUrl.RemovePassword | QUrl.FullyEncoded

        url = QUrl(self._current_url())
        url_query = QUrlQuery()
        url_query_str = urlutils.query_string(url)
        if '&' not in url_query_str and ';' in url_query_str:
            url_query.setQueryDelimiters('=', ';')
        url_query.setQuery(url_query_str)
        for key in dict(url_query.queryItems()):
            if key in config.val.url.yank_ignored_parameters:
                url_query.removeQueryItem(key)
        url.setQuery(url_query)
        return url.toString(flags)  # type: ignore[arg-type]

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('what', choices=['selection', 'url', 'pretty-url',
                                        'title', 'domain', 'inline'])
    def yank(self, what='url', inline=None,
             sel=False, keep=False, quiet=False):
        """Yank (copy) something to the clipboard or primary selection.

        Args:
            what: What to yank.

                - `url`: The current URL.
                - `pretty-url`: The URL in pretty decoded form.
                - `title`: The current page's title.
                - `domain`: The current scheme, domain, and port number.
                - `selection`: The selection under the cursor.
                - `inline`: Yank the text contained in the 'inline' argument.

            sel: Use the primary selection instead of the clipboard.
            keep: Stay in visual mode after yanking the selection.
            quiet: Don't show an information message.
            inline: A block of text, to be yanked if 'what'
                is inline and ignored otherwise.
        """
        if what == 'inline':
            s = inline
            what = 'inline block'
        elif what == 'title':
            s = self._tabbed_browser.widget.page_title(self._current_index())
        elif what == 'domain':
            port = self._current_url().port()
            s = '{}://{}{}'.format(self._current_url().scheme(),
                                   self._current_url().host(),
                                   ':' + str(port) if port > -1 else '')
        elif what in ['url', 'pretty-url']:
            s = self._yank_url(what)
            what = 'URL'  # For printing
        elif what == 'selection':
            def _selection_callback(s):
                if not s and not quiet:
                    message.info("Nothing to yank")
                    return
                self._yank_to_target(s, sel, what, keep, quiet)

            caret = self._current_widget().caret
            caret.selection(callback=_selection_callback)
            return
        else:  # pragma: no cover
            raise ValueError("Invalid value {!r} for `what'.".format(what))

        self._yank_to_target(s, sel, what, keep, quiet)

    def _yank_to_target(self, s, sel, what, keep, quiet):
        if sel and utils.supports_selection():
            target = "primary selection"
        else:
            sel = False
            target = "clipboard"

        utils.set_clipboard(s, selection=sel)
        if what != 'selection':
            if not quiet:
                message.info("Yanked {} to {}: {}".format(what, target, s))
        else:
            if not quiet:
                message.info("{} {} yanked to {}".format(
                    len(s), "char" if len(s) == 1 else "chars", target))
            if not keep:
                modeman.leave(self._win_id, KeyMode.caret, "yank selected",
                              maybe=True)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_only(self, prev=False, next_=False, force=False):
        """Close all tabs except for the current one.

        Args:
            prev: Keep tabs before the current.
            next_: Keep tabs after the current.
            force: Avoid confirmation for pinned tabs.
        """
        cmdutils.check_exclusive((prev, next_), 'pn')
        cur_idx = self._tabbed_browser.widget.currentIndex()
        assert cur_idx != -1

        def _to_close(i):
            """Helper method to check if a tab should be closed or not."""
            return not (i == cur_idx or
                        (prev and i < cur_idx) or
                        (next_ and i > cur_idx))

        # close as many tabs as we can
        first_tab = True
        pinned_tabs_cleanup = False
        for i, tab in enumerate(self._tabbed_browser.widgets()):
            if _to_close(i):
                if force or not tab.data.pinned:
                    self._tabbed_browser.close_tab(tab, new_undo=first_tab)
                    first_tab = False
                else:
                    pinned_tabs_cleanup = tab

        # Check to see if we would like to close any pinned tabs
        if pinned_tabs_cleanup:
            self._tabbed_browser.tab_close_prompt_if_pinned(
                pinned_tabs_cleanup,
                force,
                lambda: self.tab_only(
                    prev=prev, next_=next_, force=True),
                text="Are you sure you want to close pinned tabs?")

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def undo(self):
        """Re-open the last closed tab or tabs."""
        try:
            self._tabbed_browser.undo()
        except IndexError:
            raise cmdutils.CommandError("Nothing to undo!")

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def tab_prev(self, count=1):
        """Switch to the previous tab, or switch [count] tabs back.

        Args:
            count: How many tabs to switch back.
        """
        if self._count() == 0:
            # Running :tab-prev after last tab was closed
            # See https://github.com/qutebrowser/qutebrowser/issues/1448
            return
        newidx = self._current_index() - count
        if newidx >= 0:
            self._set_current_index(newidx)
        elif config.val.tabs.wrap:
            self._set_current_index(newidx % self._count())
        else:
            log.webview.debug("First tab")

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def tab_next(self, count=1):
        """Switch to the next tab, or switch [count] tabs forward.

        Args:
            count: How many tabs to switch forward.
        """
        if self._count() == 0:
            # Running :tab-next after last tab was closed
            # See https://github.com/qutebrowser/qutebrowser/issues/1448
            return
        newidx = self._current_index() + count
        if newidx < self._count():
            self._set_current_index(newidx)
        elif config.val.tabs.wrap:
            self._set_current_index(newidx % self._count())
        else:
            log.webview.debug("Last tab")

    def _resolve_buffer_index(self, index):
        """Resolve a buffer index to the tabbedbrowser and tab.

        Args:
            index: The [win_id/]index of the tab to be selected. Or a substring
                   in which case the closest match will be focused.
        """
        index_parts = index.split('/', 1)

        try:
            for part in index_parts:
                int(part)
        except ValueError:
            model = miscmodels.buffer()
            model.set_pattern(index)
            if model.count() > 0:
                index = model.data(model.first_item())
                index_parts = index.split('/', 1)
            else:
                raise cmdutils.CommandError(
                    "No matching tab for: {}".format(index))

        if len(index_parts) == 2:
            win_id = int(index_parts[0])
            idx = int(index_parts[1])
        elif len(index_parts) == 1:
            idx = int(index_parts[0])
            active_win = QApplication.activeWindow()
            if active_win is None:
                # Not sure how you enter a command without an active window...
                raise cmdutils.CommandError(
                    "No window specified and couldn't find active window!")
            win_id = active_win.win_id

        if win_id not in objreg.window_registry:
            raise cmdutils.CommandError(
                "There's no window with id {}!".format(win_id))

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)
        if not 0 < idx <= tabbed_browser.widget.count():
            raise cmdutils.CommandError(
                "There's no tab with index {}!".format(idx))

        return (tabbed_browser, tabbed_browser.widget.widget(idx-1))

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('index', completion=miscmodels.buffer)
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def buffer(self, index=None, count=None):
        """Select tab by index or url/title best match.

        Focuses window if necessary when index is given. If both index and
        count are given, use count.

        With neither index nor count given, open the qute://tabs page.

        Args:
            index: The [win_id/]index of the tab to focus. Or a substring
                   in which case the closest match will be focused.
            count: The tab index to focus, starting with 1.
        """
        if count is None and index is None:
            self.openurl('qute://tabs/', tab=True)
            return

        if count is not None:
            index = str(count)

        tabbed_browser, tab = self._resolve_buffer_index(index)

        window = tabbed_browser.widget.window()
        window.activateWindow()
        window.raise_()
        tabbed_browser.widget.setCurrentWidget(tab)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('index', choices=['last', 'stack-next', 'stack-prev'],
                       completion=miscmodels.tab_focus)
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def tab_focus(self, index: typing.Union[str, int] = None,
                  count: int = None, no_last: bool = False) -> None:
        """Select the tab given as argument/[count].

        If neither count nor index are given, it behaves like tab-next.
        If both are given, use count.

        Args:
            index: The tab index to focus, starting with 1. The special value
                   `last` focuses the last focused tab (regardless of count),
                   and `stack-prev`/`stack-next` traverse a stack of visited
                   tabs. Negative indices count from the end, such that -1 is
                   the last tab.
            count: The tab index to focus, starting with 1.
            no_last: Whether to avoid focusing last tab if already focused.
        """
        index = count if count is not None else index

        if index in {'last', 'stack-next', 'stack-prev'}:
            assert isinstance(index, str)
            self._tab_focus_stack(index)
            return
        elif index is None:
            self.tab_next()
            return

        assert isinstance(index, int)

        if index < 0:
            index = self._count() + index + 1

        if not no_last and index == self._current_index() + 1:
            self._tab_focus_stack('last', show_error=False)
            return

        if 1 <= index <= self._count():
            self._set_current_index(index - 1)
        else:
            raise cmdutils.CommandError("There's no tab with index {}!".format(
                index))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('index', choices=['+', '-'])
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def tab_move(self, index: typing.Union[str, int] = None,
                 count: int = None) -> None:
        """Move the current tab according to the argument and [count].

        If neither is given, move it to the first position.

        Args:
            index: `+` or `-` to move relative to the current tab by
                   count, or a default of 1 space.
                   A tab index to move to that index.
            count: If moving relatively: Offset.
                   If moving absolutely: New position (default: 0). This
                   overrides the index argument, if given.
        """
        if index in ['+', '-']:
            # relative moving
            new_idx = self._current_index()
            delta = 1 if count is None else count
            if index == '-':
                new_idx -= delta
            elif index == '+':  # pragma: no branch
                new_idx += delta

            if config.val.tabs.wrap:
                new_idx %= self._count()
        else:
            # absolute moving
            if count is not None:
                new_idx = count - 1
            elif index is not None:
                assert isinstance(index, int)
                new_idx = index - 1 if index >= 0 else index + self._count()
            else:
                new_idx = 0

        if not 0 <= new_idx < self._count():
            raise cmdutils.CommandError("Can't move tab to position {}!"
                                        .format(new_idx + 1))

        cur_idx = self._current_index()
        cmdutils.check_overflow(cur_idx, 'int')
        cmdutils.check_overflow(new_idx, 'int')
        self._tabbed_browser.widget.tabBar().moveTab(cur_idx, new_idx)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0, no_replace_variables=True)
    @cmdutils.argument('count', value=cmdutils.Value.count)
    @cmdutils.argument('output_messages', flag='m')
    def spawn(self, cmdline, userscript=False, verbose=False,
              output=False, output_messages=False, detach=False, count=None):
        """Spawn an external command.

        Note that the command is *not* run in a shell, so things like `$VAR` or
        `> output` won't have the desired effect.

        Args:
            userscript: Run the command as a userscript. You can use an
                        absolute path, or store the userscript in one of those
                        locations:
                            - `~/.local/share/qutebrowser/userscripts`
                              (or `$XDG_DATA_HOME`)
                            - `/usr/share/qutebrowser/userscripts`
            verbose: Show notifications when the command started/exited.
            output: Show the output in a new tab.
            output_messages: Show the output as messages.
            detach: Whether the command should be detached from qutebrowser.
            cmdline: The commandline to execute.
            count: Given to userscripts as $QUTE_COUNT.
        """
        cmdutils.check_exclusive((userscript, detach), 'ud')
        try:
            cmd, *args = shlex.split(cmdline)
        except ValueError as e:
            raise cmdutils.CommandError("Error while splitting command: "
                                        "{}".format(e))

        args = runners.replace_variables(self._win_id, args)

        log.procs.debug("Executing {} with args {}, userscript={}".format(
            cmd, args, userscript))

        @pyqtSlot()
        def _on_proc_finished():
            if output:
                tb = objreg.get('tabbed-browser', scope='window',
                                window='last-focused')
                tb.load_url(QUrl('qute://spawn-output'), newtab=True)

        if userscript:
            def _selection_callback(s):
                try:
                    runner = self._run_userscript(
                        s, cmd, args, verbose, output_messages, count)
                    runner.finished.connect(_on_proc_finished)
                except cmdutils.CommandError as e:
                    message.error(str(e))

            # ~ expansion is handled by the userscript module.
            # dirty hack for async call because of:
            # https://bugreports.qt.io/browse/QTBUG-53134
            # until it fixed or blocked async call implemented:
            # https://github.com/qutebrowser/qutebrowser/issues/3327
            caret = self._current_widget().caret
            caret.selection(callback=_selection_callback)
        else:
            cmd = os.path.expanduser(cmd)
            proc = guiprocess.GUIProcess(what='command', verbose=verbose,
                                         output_messages=output_messages,
                                         parent=self._tabbed_browser)
            if detach:
                ok = proc.start_detached(cmd, args)
                if not ok:
                    message.info("Hint: Try without --detach for a more "
                                 "detailed error")
            else:
                proc.start(cmd, args)
            proc.finished.connect(_on_proc_finished)

    def _run_userscript(self, selection, cmd, args, verbose, output_messages,
                        count):
        """Run a userscript given as argument.

        Args:
            cmd: The userscript to run.
            args: Arguments to pass to the userscript.
            verbose: Show notifications when the command started/exited.
            output_messages: Show the output as messages.
            count: Exposed to the userscript.
        """
        env = {
            'QUTE_MODE': 'command',
            'QUTE_SELECTED_TEXT': selection,
        }

        if count is not None:
            env['QUTE_COUNT'] = str(count)

        idx = self._current_index()
        if idx != -1:
            env['QUTE_TITLE'] = self._tabbed_browser.widget.page_title(idx)

        # FIXME:qtwebengine: If tab is None, run_async will fail!
        tab = self._tabbed_browser.widget.currentWidget()

        try:
            url = self._tabbed_browser.current_url()
        except qtutils.QtValueError:
            pass
        else:
            env['QUTE_URL'] = url.toString(QUrl.FullyEncoded)

        try:
            runner = userscripts.run_async(
                tab, cmd, *args, win_id=self._win_id, env=env, verbose=verbose,
                output_messages=output_messages)
        except userscripts.Error as e:
            raise cmdutils.CommandError(e)
        return runner

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def quickmark_save(self):
        """Save the current page as a quickmark."""
        quickmark_manager = objreg.get('quickmark-manager')
        quickmark_manager.prompt_save(self._current_url())

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('name', completion=miscmodels.quickmark)
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
            raise cmdutils.CommandError(str(e))
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('name', completion=miscmodels.quickmark)
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
                raise cmdutils.CommandError(str(e))
        try:
            quickmark_manager.delete(name)
        except KeyError:
            raise cmdutils.CommandError("Quickmark '{}' not found!"
                                        .format(name))

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
            url: url to save as a bookmark. If not given, use url of current
                 page.
            title: title of the new bookmark.
            toggle: remove the bookmark instead of raising an error if it
                    already exists.
        """
        if url and not title:
            raise cmdutils.CommandError('Title must be provided if url has '
                                        'been provided')
        bookmark_manager = objreg.get('bookmark-manager')
        if not url:
            url = self._current_url()
        else:
            try:
                url = urlutils.fuzzy_url(url)
            except urlutils.InvalidUrlError as e:
                raise cmdutils.CommandError(e)
        if not title:
            title = self._current_title()
        try:
            was_added = bookmark_manager.add(url, title, toggle=toggle)
        except urlmarks.Error as e:
            raise cmdutils.CommandError(str(e))
        else:
            msg = "Bookmarked {}" if was_added else "Removed bookmark {}"
            message.info(msg.format(url.toDisplayString()))

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('url', completion=miscmodels.bookmark)
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
            raise cmdutils.CommandError(e)
        self._open(qurl, tab, bg, window)
        if delete:
            self.bookmark_del(url)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    @cmdutils.argument('url', completion=miscmodels.bookmark)
    def bookmark_del(self, url=None):
        """Delete a bookmark.

        Args:
            url: The url of the bookmark to delete. If not given, use the
                 current page's url.
        """
        if url is None:
            url = self._current_url().toString(QUrl.RemovePassword |
                                               QUrl.FullyEncoded)
        try:
            objreg.get('bookmark-manager').delete(url)
        except KeyError:
            raise cmdutils.CommandError("Bookmark '{}' not found!".format(url))
        message.info("Removed bookmark {}".format(url))

    @cmdutils.register(instance='command-dispatcher', name='inspector',
                       scope='window')
    def toggle_inspector(self):
        """Toggle the web inspector.

        Note: Due to a bug in Qt, the inspector will show incorrect request
        headers in the network tab.
        """
        tab = self._current_widget()
        # FIXME:qtwebengine have a proper API for this
        page = tab._widget.page()  # pylint: disable=protected-access

        try:
            if tab.data.inspector is None:
                tab.data.inspector = inspector.create()
                tab.data.inspector.inspect(page)
                tab.data.inspector.show()
            else:
                tab.data.inspector.toggle(page)
        except inspector.WebInspectorError as e:
            raise cmdutils.CommandError(e)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def download(self, url=None, *, mhtml_=False, dest=None):
        """Download a given URL, or current page if no URL given.

        Args:
            url: The URL to download. If not given, download the current page.
            dest: The file path to write the download to, or None to ask.
            mhtml_: Download the current page and all assets as mhtml file.
        """
        # FIXME:qtwebengine do this with the QtWebEngine download manager?
        download_manager = objreg.get('qtnetwork-download-manager')
        target = None
        if dest is not None:
            dest = downloads.transform_path(dest)
            if dest is None:
                raise cmdutils.CommandError("Invalid target filename")
            target = downloads.FileDownloadTarget(dest)

        tab = self._current_widget()

        if url:
            if mhtml_:
                raise cmdutils.CommandError("Can only download the current "
                                            "page as mhtml.")
            url = urlutils.qurl_from_user_input(url)
            urlutils.raise_cmdexc_if_invalid(url)
            download_manager.get(url, target=target)
        elif mhtml_:
            tab = self._current_widget()
            if tab.backend == usertypes.Backend.QtWebEngine:
                webengine_download_manager = objreg.get(
                    'webengine-download-manager')
                try:
                    webengine_download_manager.get_mhtml(tab, target)
                except browsertab.UnsupportedOperationError as e:
                    raise cmdutils.CommandError(e)
            else:
                download_manager.get_mhtml(tab, target)
        else:
            qnam = tab.private_api.networkaccessmanager()

            suggested_fn = downloads.suggested_fn_from_title(
                self._current_url().path(), tab.title()
            )

            download_manager.get(
                self._current_url(),
                qnam=qnam,
                target=target,
                suggested_fn=suggested_fn
            )

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def view_source(self, edit=False, pygments=False):
        """Show the source of the current page in a new tab.

        Args:
            edit: Edit the source in the editor instead of opening a tab.
            pygments: Use pygments to generate the view. This is always
                      the case for QtWebKit. For QtWebEngine it may display
                      slightly different source.
                      Some JavaScript processing may be applied.
        """
        tab = self._current_widget()
        try:
            current_url = self._current_url()
        except cmdutils.CommandError as e:
            message.error(str(e))
            return

        if current_url.scheme() == 'view-source' or tab.data.viewing_source:
            raise cmdutils.CommandError("Already viewing source!")

        if edit:
            ed = editor.ExternalEditor(self._tabbed_browser)
            tab.dump_async(ed.edit)
        else:
            tab.action.show_source(pygments)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def history(self, tab=True, bg=False, window=False):
        """Show browsing history.

        Args:
            tab: Open in a new tab.
            bg: Open in a background tab.
            window: Open in a new window.
        """
        url = QUrl('qute://history/')
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', name='help',
                       scope='window')
    @cmdutils.argument('topic', completion=miscmodels.helptopic)
    def show_help(self, tab=False, bg=False, window=False, topic=None):
        r"""Show help about a command or setting.

        Args:
            tab: Open in a new tab.
            bg: Open in a background tab.
            window: Open in a new window.
            topic: The topic to show help for.

                   - :__command__ for commands.
                   - __section__.__option__ for settings.
        """
        if topic is None:
            path = 'index.html'
        elif topic.startswith(':'):
            command = topic[1:]
            if command not in objects.commands:
                raise cmdutils.CommandError("Invalid command {}!".format(
                    command))
            path = 'commands.html#{}'.format(command)
        elif topic in configdata.DATA:
            path = 'settings.html#{}'.format(topic)
        else:
            raise cmdutils.CommandError("Invalid help topic {}!".format(topic))
        url = QUrl('qute://help/{}'.format(path))
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def messages(self, level='info', plain=False, tab=False, bg=False,
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
            raise cmdutils.CommandError("Invalid log level {}!".format(level))
        if plain:
            url = QUrl('qute://plainlog?level={}'.format(level))
        else:
            url = QUrl('qute://log?level={}'.format(level))
        self._open(url, tab, bg, window)

    def _open_editor_cb(self, elem):
        """Open editor after the focus elem was found in open_editor."""
        if elem is None:
            message.error("No element focused!")
            return
        if not elem.is_editable(strict=True):
            message.error("Focused element is not editable!")
            return

        text = elem.value()
        if text is None:
            message.error("Could not get text from the focused element.")
            return
        assert isinstance(text, str), text

        caret_position = elem.caret_position()

        ed = editor.ExternalEditor(watch=True, parent=self._tabbed_browser)
        ed.file_updated.connect(functools.partial(
            self.on_file_updated, ed, elem))
        ed.editing_finished.connect(lambda: mainwindow.raise_window(
            objreg.last_focused_window(), alert=False))
        ed.edit(text, caret_position)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def open_editor(self):
        """Open an external editor with the currently selected form field.

        The editor which should be launched can be configured via the
        `editor.command` config option.
        """
        tab = self._current_widget()
        tab.elements.find_focused(self._open_editor_cb)

    def on_file_updated(self, ed, elem, text):
        """Write the editor text into the form field and clean up tempfile.

        Callback for GUIProcess when the edited text was updated.

        Args:
            elem: The WebElementWrapper which was modified.
            text: The new text to insert.
        """
        try:
            elem.set_value(text)
            # Kick off js handlers to trick them into thinking there was input.
            elem.dispatch_event("input", bubbles=True)
        except webelem.OrphanedError:
            message.error('Edited element vanished')
            ed.backup()
        except webelem.Error as e:
            message.error(str(e))
            ed.backup()

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
                message.info("Search hit BOTTOM, continuing at TOP")
            elif going_up and tab.scroller.pos_px().y() > old_scroll_pos.y():
                message.info("Search hit TOP, continuing at BOTTOM")
        else:
            message.warning("Text '{}' not found on page!".format(text),
                            replace=True)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0)
    def search(self, text="", reverse=False):
        """Search for a text on the current page. With no text, clear results.

        Args:
            text: The text to search for.
            reverse: Reverse search direction.
        """
        tab = self._current_widget()

        if not text:
            if tab.search.search_displayed:
                tab.search.clear()
            return

        options = {
            'ignore_case': config.val.search.ignore_case,
            'reverse': reverse,
            'wrap': config.val.search.wrap,
        }

        self._tabbed_browser.search_text = text
        self._tabbed_browser.search_options = dict(options)

        cb = functools.partial(self._search_cb, tab=tab,
                               old_scroll_pos=tab.scroller.pos_px(),
                               options=options, text=text, prev=False)
        options['result_cb'] = cb

        tab.scroller.before_jump_requested.emit()
        tab.search.search(text, **options)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def search_next(self, count=1):
        """Continue the search to the ([count]th) next term.

        Args:
            count: How many elements to ignore.
        """
        tab = self._current_widget()
        window_text = self._tabbed_browser.search_text
        window_options = self._tabbed_browser.search_options

        if window_text is None:
            raise cmdutils.CommandError("No search done yet.")

        tab.scroller.before_jump_requested.emit()

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

    @cmdutils.register(instance='command-dispatcher', scope='window')
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def search_prev(self, count=1):
        """Continue the search to the ([count]th) previous term.

        Args:
            count: How many elements to ignore.
        """
        tab = self._current_widget()
        window_text = self._tabbed_browser.search_text
        window_options = self._tabbed_browser.search_options

        if window_text is None:
            raise cmdutils.CommandError("No search done yet.")

        tab.scroller.before_jump_requested.emit()

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

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       maxsplit=0, no_cmd_split=True)
    def jseval(self, js_code: str, file: bool = False, quiet: bool = False, *,
               world: typing.Union[usertypes.JsWorld, int] = None) -> None:
        """Evaluate a JavaScript string.

        Args:
            js_code: The string/file to evaluate.
            file: Interpret js-code as a path to a file.
                  If the path is relative, the file is searched in a js/ subdir
                  in qutebrowser's data dir, e.g.
                  `~/.local/share/qutebrowser/js`.
            quiet: Don't show resulting JS object.
            world: Ignored on QtWebKit. On QtWebEngine, a world ID or name to
                   run the snippet in.
        """
        if world is None:
            world = usertypes.JsWorld.jseval

        if quiet:
            jseval_cb = None
        else:
            def jseval_cb(out):
                """Show the data returned from JS."""
                if out is None:
                    # Getting the actual error (if any) seems to be difficult.
                    # The error does end up in
                    # BrowserPage.javaScriptConsoleMessage(), but
                    # distinguishing between :jseval errors and errors from the
                    # webpage is not trivial...
                    message.info('No output or error')
                else:
                    # The output can be a string, number, dict, array, etc. But
                    # *don't* output too much data, as this will make
                    # qutebrowser hang
                    out = str(out)
                    if len(out) > 5000:
                        out = out[:5000] + ' [...trimmed...]'
                    message.info(out)

        if file:
            path = os.path.expanduser(js_code)
            if not os.path.isabs(path):
                path = os.path.join(standarddir.data(), 'js', path)

            try:
                with open(path, 'r', encoding='utf-8') as f:
                    js_code = f.read()
            except OSError as e:
                raise cmdutils.CommandError(str(e))

        widget = self._current_widget()
        try:
            widget.run_js_async(js_code, callback=jseval_cb, world=world)
        except browsertab.WebTabError as e:
            raise cmdutils.CommandError(str(e))

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
            sequence = keyutils.KeySequence.parse(keystring)
        except keyutils.KeyParseError as e:
            raise cmdutils.CommandError(str(e))

        for keyinfo in sequence:
            press_event = keyinfo.to_event(QEvent.KeyPress)
            release_event = keyinfo.to_event(QEvent.KeyRelease)

            if global_:
                window = QApplication.focusWindow()
                if window is None:
                    raise cmdutils.CommandError("No focused window!")
                QApplication.postEvent(window, press_event)
                QApplication.postEvent(window, release_event)
            else:
                tab = self._current_widget()
                tab.send_event(press_event)
                tab.send_event(release_event)

    @cmdutils.register(instance='command-dispatcher', scope='window',
                       debug=True, backend=usertypes.Backend.QtWebKit)
    def debug_clear_ssl_errors(self):
        """Clear remembered SSL error answers."""
        self._current_widget().private_api.clear_ssl_errors()

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def edit_url(self, url=None, bg=False, tab=False, window=False,
                 private=False, related=False):
        """Navigate to a url formed in an external editor.

        The editor which should be launched can be configured via the
        `editor.command` config option.

        Args:
            url: URL to edit; defaults to the current page url.
            bg: Open in a new background tab.
            tab: Open in a new tab.
            window: Open in a new window.
            private: Open a new window in private browsing mode.
            related: If opening a new tab, position the tab as related to the
                     current one (like clicking on a link).
        """
        cmdutils.check_exclusive((tab, bg, window), 'tbw')

        old_url = self._current_url().toString()

        ed = editor.ExternalEditor(self._tabbed_browser)

        # Passthrough for openurl args (e.g. -t, -b, -w)
        ed.file_updated.connect(functools.partial(
            self._open_if_changed, old_url=old_url, bg=bg, tab=tab,
            window=window, private=private, related=related))

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
                         window=False, private=False, related=False):
        """Open a URL unless it's already open in the tab.

        Args:
            old_url: The original URL to compare against.
            url: The URL to open.
            bg: Open in a new background tab.
            tab: Open in a new tab.
            window: Open in a new window.
            private: Open a new window in private browsing mode.
            related: If opening a new tab, position the tab as related to the
                     current one (like clicking on a link).
        """
        if bg or tab or window or private or related or url != old_url:
            self.openurl(url=url, bg=bg, tab=tab, window=window,
                         private=private, related=related)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def fullscreen(self, leave=False, enter=False):
        """Toggle fullscreen mode.

        Args:
            leave: Only leave fullscreen if it was entered by the page.
            enter: Activate fullscreen and do not toggle if it is already
                   active.
        """
        if leave:
            tab = self._current_widget()
            try:
                tab.action.exit_fullscreen()
            except browsertab.UnsupportedOperationError:
                pass
            return

        window = self._tabbed_browser.widget.window()

        if not window.isFullScreen():
            window.state_before_fullscreen = window.windowState()
        if enter:
            window.setWindowState(window.windowState() | Qt.WindowFullScreen)
        else:
            window.setWindowState(window.windowState() ^ Qt.WindowFullScreen)

        log.misc.debug('state before fullscreen: {}'.format(
            debug.qflags_key(Qt, window.state_before_fullscreen)))
