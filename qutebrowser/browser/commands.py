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

"""Command dispatcher for TabbedBrowser."""

import re
import os
import subprocess
import posixpath
import functools

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QClipboard
from PyQt5.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebInspector
import pygments
import pygments.lexers
import pygments.formatters

from qutebrowser.commands import userscripts, cmdexc, cmdutils
from qutebrowser.config import config
from qutebrowser.browser import quickmarks, webelem
from qutebrowser.utils import (message, editor, usertypes, log, qtutils,
                               urlutils, objreg, utils)


class CommandDispatcher:

    """Command dispatcher for TabbedBrowser.

    Contains all commands which are related to the current tab.

    We can't simply add these commands to BrowserTab directly and use
    currentWidget() for TabbedBrowser.cmd because at the time
    cmdutils.register() decorators are run, currentWidget() will return None.

    Attributes:
        _editor: The ExternalEditor object.
        _win_id: The window ID the CommandDispatcher is associated with.
        _timers: A list of timers for :later
    """

    def __init__(self, win_id):
        self._editor = None
        self._win_id = win_id
        self._timers = []

    def __repr__(self):
        return utils.get_repr(self)

    def _tabbed_browser(self):
        """Convienence method to get the right tabbed-browser."""
        return objreg.get('tabbed-browser', scope='window',
                          window=self._win_id)

    def _count(self):
        """Convenience method to get the widget count."""
        return self._tabbed_browser().count()

    def _set_current_index(self, idx):
        """Convenience method to set the current widget index."""
        return self._tabbed_browser().setCurrentIndex(idx)

    def _current_index(self):
        """Convenience method to get the current widget index."""
        return self._tabbed_browser().currentIndex()

    def _current_url(self):
        """Convenience method to get the current url."""
        return self._tabbed_browser().current_url()

    def _current_widget(self):
        """Get the currently active widget from a command."""
        widget = self._tabbed_browser().currentWidget()
        if widget is None:
            raise cmdexc.CommandError("No WebView available yet!")
        return widget

    def _open(self, url, tab, background, window):
        """Helper function to open a page.

        Args:
            url: The URL to open as QUrl.
            tab: Whether to open in a new tab.
            background: Whether to open in the background.
            window: Whether to open in a new window
        """
        tabbed_browser = self._tabbed_browser()
        if sum(1 for e in (tab, background, window) if e) > 1:
            raise cmdexc.CommandError("Only one of -t/-b/-w can be given!")
        elif window:
            # We have to import this here to avoid a circular import.
            from qutebrowser.widgets import mainwindow
            win_id = mainwindow.create_window()
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
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
        tabbed_browser = self._tabbed_browser()
        if count is None:
            return tabbed_browser.currentWidget()
        elif 1 <= count <= self._count():
            cmdutils.check_overflow(count + 1, 'int')
            return tabbed_browser.widget(count - 1)
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
            tab = objreg.get('last-focused-tab')
        except KeyError:
            raise cmdexc.CommandError("No last focused tab!")
        idx = self._tabbed_browser().indexOf(tab)
        if idx == -1:
            raise cmdexc.CommandError("Last focused tab vanished!")
        self._set_current_index(idx)

    def _editor_cleanup(self, oshandle, filename):
        """Clean up temporary file when the editor was closed."""
        os.close(oshandle)
        try:
            os.remove(filename)
        except PermissionError:
            raise cmdexc.CommandError("Failed to delete tempfile...")

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_close(self, count=None):
        """Close the current/[count]th tab.

        Args:
            count: The tab index to close, or None

        Emit:
            quit: If last tab was closed and last-close in config is set to
                  quit.
        """
        tab = self._cntwidget(count)
        if tab is None:
            return
        self._tabbed_browser().close_tab(tab)

    @cmdutils.register(instance='command-dispatcher', name='open',
                       split=False, scope='window')
    def openurl(self, url, bg=False, tab=False, window=False, count=None):
        """Open a URL in the current/[count]th tab.

        Args:
            url: The URL to open.
            bg: Open in a new background tab.
            tab: Open in a new tab.
            window: Open in a new window.
            count: The tab index to open the URL in, or None.
        """
        try:
            url = urlutils.fuzzy_url(url)
        except urlutils.FuzzyUrlError as e:
            raise cmdexc.CommandError(e)
        if tab or bg or window:
            self._open(url, tab, bg, window)
        else:
            curtab = self._cntwidget(count)
            if curtab is None:
                if count is None:
                    # We want to open a URL in the current tab, but none exists
                    # yet.
                    self._tabbed_browser().tabopen(url)
                else:
                    # Explicit count with a tab that doesn't exist.
                    return
            else:
                curtab.openurl(url)

    @cmdutils.register(instance='command-dispatcher', name='reload',
                       scope='window')
    def reloadpage(self, count=None):
        """Reload the current/[count]th tab.

        Args:
            count: The tab index to reload, or None.
        """
        tab = self._cntwidget(count)
        if tab is not None:
            tab.reload()

    @cmdutils.register(instance='command-dispatcher', scope='window')
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
                diag.paintRequested.connect(tab.print)
                diag.exec_()
            else:
                diag = QPrintDialog()
                diag.setAttribute(Qt.WA_DeleteOnClose)
                diag.open(lambda: tab.print(diag.printer()))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_clone(self, bg=False):
        """Duplicate the current tab.

        Args:
            bg: Open in a background tab.

        Return:
            The new QWebView.
        """
        curtab = self._current_widget()
        tabbed_browser = self._tabbed_browser()
        newtab = tabbed_browser.tabopen(background=bg, explicit=True)
        history = qtutils.serialize(curtab.history())
        qtutils.deserialize(history, newtab.history())
        return newtab

    def _back_forward(self, tab, bg, count, forward):
        """Helper function for :back/:forward."""
        if tab or bg:
            widget = self.tab_clone(bg)
        else:
            widget = self._current_widget()
        for _ in range(count):
            if forward:
                widget.go_forward()
            else:
                widget.go_back()

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def back(self, tab=False, bg=False, count=1):
        """Go back in the history of the current tab.

        Args:
            tab: Go back in a new tab.
            bg: Go back in a background tab.
            count: How many pages to go back.
        """
        self._back_forward(tab, bg, count, forward=False)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def forward(self, tab=False, bg=False, count=1):
        """Go forward in the history of the current tab.

        Args:
            tab: Go forward in a new tab.
            bg: Go back in a background tab.
            count: How many pages to go forward.
        """
        self._back_forward(tab, bg, count, forward=True)

    def _navigate_incdec(self, url, tab, incdec):
        """Helper method for :navigate when `where' is increment/decrement.

        Args:
            url: The current url.
            tab: Whether to open the link in a new tab.
            incdec: Either 'increment' or 'decrement'.
        """
        encoded = bytes(url.toEncoded()).decode('ascii')
        # Get the last number in a string
        match = re.match(r'(.*\D|^)(\d+)(.*)', encoded)
        if not match:
            raise cmdexc.CommandError("No number found in URL!")
        pre, number, post = match.groups()
        if not number:
            raise cmdexc.CommandError("No number found in URL!")
        try:
            val = int(number)
        except ValueError:
            raise cmdexc.CommandError("Could not parse number '{}'.".format(
                number))
        if incdec == 'decrement':
            if val <= 0:
                raise cmdexc.CommandError("Can't decrement {}!".format(val))
            val -= 1
        elif incdec == 'increment':
            val += 1
        else:
            raise ValueError("Invalid value {} for indec!".format(incdec))
        urlstr = ''.join([pre, str(val), post]).encode('ascii')
        new_url = QUrl.fromEncoded(urlstr)
        self._open(new_url, tab, background=False, window=False)

    def _navigate_up(self, url, tab):
        """Helper method for :navigate when `where' is up.

        Args:
            url: The current url.
            tab: Whether to open the link in a new tab.
        """
        path = url.path()
        if not path or path == '/':
            raise cmdexc.CommandError("Can't go up!")
        new_path = posixpath.join(path, posixpath.pardir)
        url.setPath(new_path)
        self._open(url, tab, background=False, window=False)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def navigate(self, where: ('prev', 'next', 'up', 'increment', 'decrement'),
                 tab=False):
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
        """
        widget = self._current_widget()
        frame = widget.page().currentFrame()
        url = self._current_url()
        if frame is None:
            raise cmdexc.CommandError("No frame focused!")
        hintmanager = objreg.get('hintmanager', scope='tab')
        if where == 'prev':
            hintmanager.follow_prevnext(frame, url, prev=True, newtab=tab)
        elif where == 'next':
            hintmanager.follow_prevnext(frame, url, prev=False, newtab=tab)
        elif where == 'up':
            self._navigate_up(url, tab)
        elif where in ('decrement', 'increment'):
            self._navigate_incdec(url, tab, where)
        else:
            raise ValueError("Got called with invalid value {} for "
                             "`where'.".format(where))

    @cmdutils.register(instance='command-dispatcher', hide=True,
                       scope='window')
    def scroll(self, dx: float, dy: float, count=1):
        """Scroll the current tab by 'count * dx/dy'.

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
                       scope='window')
    def scroll_perc(self, perc: float=None,
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
                       scope='window')
    def scroll_page(self, x: float, y: float, count=1):
        """Scroll the frame page-wise.

        Args:
            x: How many pages to scroll to the right.
            y: How many pages to scroll down.
            count: multiplier
        """
        frame = self._current_widget().page().currentFrame()
        size = frame.geometry()
        dx = count * x * size.width()
        dy = count * y * size.height()
        cmdutils.check_overflow(dx, 'int')
        cmdutils.check_overflow(dy, 'int')
        frame.scroll(dx, dy)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def yank(self, title=False, sel=False):
        """Yank the current URL/title to the clipboard or primary selection.

        Args:
            sel: Use the primary selection instead of the clipboard.
            title: Yank the title instead of the URL.
        """
        clipboard = QApplication.clipboard()
        if title:
            s = self._tabbed_browser().tabText(self._current_index())
        else:
            s = self._current_url().toString(
                QUrl.FullyEncoded | QUrl.RemovePassword)
        if sel and clipboard.supportsSelection():
            mode = QClipboard.Selection
            target = "primary selection"
        else:
            mode = QClipboard.Clipboard
            target = "clipboard"
        log.misc.debug("Yanking to {}: '{}'".format(target, s))
        clipboard.setText(s, mode)
        what = 'Title' if title else 'URL'
        message.info(self._win_id, "{} yanked to {}".format(what, target))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def zoom_in(self, count=1):
        """Increase the zoom level for the current tab.

        Args:
            count: How many steps to zoom in.
        """
        tab = self._current_widget()
        tab.zoom(count)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def zoom_out(self, count=1):
        """Decrease the zoom level for the current tab.

        Args:
            count: How many steps to zoom out.
        """
        tab = self._current_widget()
        tab.zoom(-count)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def zoom(self, zoom=None, count=None):
        """Set the zoom level for the current tab.

        The zoom can be given as argument or as [count]. If neither of both is
        given, the zoom is set to 100%.

        Args:
            zoom: The zoom percentage to set.
            count: The zoom percentage to set.
        """
        try:
            level = cmdutils.arg_or_count(zoom, count, default=100)
        except ValueError as e:
            raise cmdexc.CommandError(e)
        tab = self._current_widget()
        tab.zoom_perc(level)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_only(self):
        """Close all tabs except for the current one."""
        tabbed_browser = self._tabbed_browser()
        for tab in tabbed_browser.widgets():
            if tab is self._current_widget():
                continue
            tabbed_browser.close_tab(tab)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def undo(self):
        """Re-open a closed tab (optionally skipping [count] closed tabs)."""
        try:
            self._tabbed_browser().undo()
        except IndexError:
            raise cmdexc.CommandError("Nothing to undo!")

    @cmdutils.register(instance='command-dispatcher', scope='window')
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

    @cmdutils.register(instance='command-dispatcher', scope='window')
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
        except urlutils.FuzzyUrlError as e:
            raise cmdexc.CommandError(e)
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_focus(self, index: (int, 'last')=None, count=None):
        """Select the tab given as argument/[count].

        Args:
            index: The tab index to focus, starting with 1. The special value
                   `last` focuses the last focused tab.
            count: The tab index to focus, starting with 1.
        """
        if index == 'last':
            self._tab_focus_last()
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

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def tab_move(self, direction: ('+', '-')=None, count=None):
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
        tabbed_browser = self._tabbed_browser()
        tab = self._current_widget()
        cur_idx = self._current_index()
        icon = tabbed_browser.tabIcon(cur_idx)
        label = tabbed_browser.tabText(cur_idx)
        cmdutils.check_overflow(cur_idx, 'int')
        cmdutils.check_overflow(new_idx, 'int')
        tabbed_browser.setUpdatesEnabled(False)
        try:
            tabbed_browser.removeTab(cur_idx)
            tabbed_browser.insertTab(new_idx, tab, icon, label)
            self._set_current_index(new_idx)
        finally:
            tabbed_browser.setUpdatesEnabled(True)

    @cmdutils.register(instance='command-dispatcher', split=False,
                       scope='window')
    def spawn(self, *args):
        """Spawn a command in a shell.

        Note the {url} variable which gets replaced by the current URL might be
        useful here.

        //

        We use subprocess rather than Qt's QProcess here because we really
        don't care about the process anymore as soon as it's spawned.

        Args:
            *args: The commandline to execute.
        """
        log.procs.debug("Executing: {}".format(args))
        subprocess.Popen(args)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def home(self):
        """Open main startpage in current tab."""
        self.openurl(config.get('general', 'startpage')[0])

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def run_userscript(self, cmd, *args: {'nargs': '*'}):
        """Run an userscript given as argument.

        Args:
            cmd: The userscript to run.
            args: Arguments to pass to the userscript.
        """
        userscripts.run(cmd, *args, url=self._current_url(),
                        win_id=self._win_id)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def quickmark_save(self):
        """Save the current page as a quickmark."""
        quickmarks.prompt_save(self._win_id, self._current_url())

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def quickmark_load(self, name, tab=False, bg=False, window=False):
        """Load a quickmark.

        Args:
            name: The name of the quickmark to load.
            tab: Load the quickmark in a new tab.
            bg: Load the quickmark in a new background tab.
            window: Load the quickmark in a new window.
        """
        urlstr = quickmarks.get(name)
        url = QUrl(urlstr)
        if not url.isValid():
            raise cmdexc.CommandError("Invalid URL {} ({})".format(
                urlstr, url.errorString()))
        self._open(url, tab, bg, window)

    @cmdutils.register(instance='command-dispatcher', name='inspector',
                       scope='window')
    def toggle_inspector(self):
        """Toggle the web inspector."""
        cur = self._current_widget()
        if cur.inspector is None:
            if not config.get('general', 'developer-extras'):
                raise cmdexc.CommandError(
                    "Please enable developer-extras before using the "
                    "webinspector!")
            cur.inspector = QWebInspector()
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
    def download_page(self):
        """Download the current page."""
        page = self._current_widget().page()
        objreg.get('download-manager').get(self._current_url(), page)

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def view_source(self):
        """Show the source of the current page."""
        # pylint doesn't seem to like pygments...
        # pylint: disable=no-member
        widget = self._current_widget()
        if widget.viewing_source:
            raise cmdexc.CommandError("Already viewing source!")
        frame = widget.page().currentFrame()
        html = frame.toHtml()
        lexer = pygments.lexers.HtmlLexer()
        formatter = pygments.formatters.HtmlFormatter(
            full=True, linenos='table')
        highlighted = pygments.highlight(html, lexer, formatter)
        tab = self._tabbed_browser().tabopen(explicit=True)
        tab.setHtml(highlighted, self._current_url())
        tab.viewing_source = True

    @cmdutils.register(instance='command-dispatcher', name='help',
                       completion=[usertypes.Completion.helptopic],
                       scope='window')
    def show_help(self, topic=None):
        r"""Show help about a command or setting.

        Args:
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
            except config.NoSectionError:
                raise cmdexc.CommandError("Invalid section {}!".format(
                    parts[0]))
            except config.NoOptionError:
                raise cmdexc.CommandError("Invalid option {}!".format(
                    parts[1]))
            path = 'settings.html#{}'.format(topic.replace('->', '-'))
        else:
            raise cmdexc.CommandError("Invalid help topic {}!".format(topic))
        self.openurl('qute://help/{}'.format(path))

    @cmdutils.register(instance='command-dispatcher', scope='window')
    def later(self, ms: int, *command):
        """Execute a command after some time.

        Args:
            ms: How many milliseconds to wait.
            *command: The command to run, with optional args.
        """
        timer = usertypes.Timer(name='later')
        timer.setSingleShot(True)
        if ms < 0:
            raise cmdexc.CommandError("I can't run something in the past!")
        try:
            timer.setInterval(ms)
        except OverflowError:
            raise cmdexc.CommandError("Numeric argument is too large for "
                                      "internal int representation.")
        self._timers.append(timer)
        cmdline = ' '.join(command)
        commandrunner = objreg.get('command-runner', scope='window',
                                   window=self._win_id)
        timer.timeout.connect(
            functools.partial(commandrunner.run_safely, cmdline))
        timer.timeout.connect(lambda: self._timers.remove(timer))
        timer.start()

    @cmdutils.register(instance='command-dispatcher',
                       modes=[usertypes.KeyMode.insert],
                       hide=True, scope='window')
    def open_editor(self):
        """Open an external editor with the currently selected form field.

        The editor which should be launched can be configured via the
        `general -> editor` config option.

        //

        We use QProcess rather than subprocess here because it makes it a lot
        easier to execute some code as soon as the process has been finished
        and do everything async.
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
            self._win_id, self._tabbed_browser())
        self._editor.editing_finished.connect(
            functools.partial(self.on_editing_finished, elem))
        self._editor.edit(text)

    def on_editing_finished(self, elem, text):
        """Write the editor text into the form field and clean up tempfile.

        Callback for QProcess when the editor was closed.

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
