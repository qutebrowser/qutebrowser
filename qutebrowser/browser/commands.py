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

import os
import subprocess
from functools import partial

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QClipboard
from PyQt5.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebInspector

from qutebrowser.commands import userscripts, cmdexc, cmdutils
from qutebrowser.config import config
from qutebrowser.browser import hints, quickmarks
from qutebrowser.utils import (message, webelem, editor, usertypes, log,
                               qtutils, urlutils)


class CommandDispatcher:

    """Command dispatcher for TabbedBrowser.

    Contains all commands which are related to the current tab.

    We can't simply add these commands to BrowserTab directly and use
    currentWidget() for TabbedBrowser.cmd because at the time
    cmdutils.register() decorators are run, currentWidget() will return None.

    Attributes:
        _tabs: The TabbedBrowser object.
        _editor: The ExternalEditor object.
    """

    def __init__(self, parent):
        """Constructor.

        Args:
            parent: The TabbedBrowser for this dispatcher.
        """
        self._tabs = parent
        self._editor = None

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
            perc = int(count)
        else:
            perc = float(perc)
        perc = qtutils.check_overflow(perc, 'int', fatal=False)
        frame = self._tabs.currentWidget().page().currentFrame()
        m = frame.scrollBarMaximum(orientation)
        if m == 0:
            return
        frame.setScrollBarValue(orientation, int(m * perc / 100))

    def _prevnext(self, prev, newtab):
        """Inner logic for {tab,}{prev,next}page."""
        widget = self._tabs.currentWidget()
        frame = widget.page().currentFrame()
        if frame is None:
            raise cmdexc.CommandError("No frame focused!")
        widget.hintmanager.follow_prevnext(frame, self._tabs.current_url(),
                                           prev, newtab)

    def _tab_move_absolute(self, idx):
        """Get an index for moving a tab absolutely.

        Args:
            idx: The index to get, as passed as count.
        """
        if idx is None:
            return 0
        elif idx == 0:
            return self._tabs.count() - 1
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
            return self._tabs.currentIndex() - delta
        elif direction == '+':
            return self._tabs.currentIndex() + delta

    def _tab_focus_last(self):
        """Select the tab which was last focused."""
        if self._tabs.last_focused is None:
            raise cmdexc.CommandError("No last focused tab!")
        idx = self._tabs.indexOf(self._tabs.last_focused)
        if idx == -1:
            raise cmdexc.CommandError("Last focused tab vanished!")
        self._tabs.setCurrentIndex(idx)

    def _editor_cleanup(self, oshandle, filename):
        """Clean up temporary file when the editor was closed."""
        os.close(oshandle)
        try:
            os.remove(filename)
        except PermissionError:
            raise cmdexc.CommandError("Failed to delete tempfile...")

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_close(self, count=None):
        """Close the current/[count]th tab.

        Args:
            count: The tab index to close, or None

        Emit:
            quit: If last tab was closed and last-close in config is set to
                  quit.
        """
        tab = self._tabs.cntwidget(count)
        if tab is None:
            return
        self._tabs.close_tab(tab)

    @cmdutils.register(instance='mainwindow.tabs.cmd', name='open',
                       split=False)
    def openurl(self, urlstr, count=None):
        """Open a URL in the current/[count]th tab.

        Args:
            urlstr: The URL to open, as string.
            count: The tab index to open the URL in, or None.
        """
        tab = self._tabs.cntwidget(count)
        try:
            url = urlutils.fuzzy_url(urlstr)
        except urlutils.FuzzyUrlError as e:
            raise cmdexc.CommandError(e)
        if tab is None:
            if count is None:
                # We want to open a URL in the current tab, but none exists
                # yet.
                self._tabs.tabopen(url)
            else:
                # Explicit count with a tab that doesn't exist.
                return
        else:
            tab.openurl(url)

    @cmdutils.register(instance='mainwindow.tabs.cmd', name='reload')
    def reloadpage(self, count=None):
        """Reload the current/[count]th tab.

        Args:
            count: The tab index to reload, or None.
        """
        tab = self._tabs.cntwidget(count)
        if tab is not None:
            tab.reload()

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def stop(self, count=None):
        """Stop loading in the current/[count]th tab.

        Args:
            count: The tab index to stop, or None.
        """
        tab = self._tabs.cntwidget(count)
        if tab is not None:
            tab.stop()

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def print_preview(self, count=None):
        """Preview printing of the current/[count]th tab.

        Args:
            count: The tab index to print, or None.
        """
        if not qtutils.check_print_compat():
            raise cmdexc.CommandError(
                "Printing on Qt < 5.3.0 on Windows is broken, please upgrade!")
        tab = self._tabs.cntwidget(count)
        if tab is not None:
            preview = QPrintPreviewDialog()
            preview.setAttribute(Qt.WA_DeleteOnClose)
            preview.paintRequested.connect(tab.print)
            preview.exec_()

    @cmdutils.register(instance='mainwindow.tabs.cmd', name='print')
    def printpage(self, count=None):
        """Print the current/[count]th tab.

        Args:
            count: The tab index to print, or None.
        """
        if not qtutils.check_print_compat():
            raise cmdexc.CommandError(
                "Printing on Qt < 5.3.0 on Windows is broken, please upgrade!")
        tab = self._tabs.cntwidget(count)
        if tab is not None:
            printdiag = QPrintDialog()
            printdiag.setAttribute(Qt.WA_DeleteOnClose)
            printdiag.open(lambda: tab.print(printdiag.printer()))

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def back(self, count=1):
        """Go back in the history of the current tab.

        Args:
            count: How many pages to go back.
        """
        for _ in range(count):
            self._tabs.currentWidget().go_back()

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def forward(self, count=1):
        """Go forward in the history of the current tab.

        Args:
            count: How many pages to go forward.
        """
        for _ in range(count):
            self._tabs.currentWidget().go_forward()

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def hint(self, group='all', target='normal', *args):
        """Start hinting.

        Args:
            group: The hinting mode to use.

                - `all`: All clickable elements.
                - `links`: Only links.
                - `images`: Only images.

            target: What to do with the selected element.

                - `normal`: Open the link in the current tab.
                - `tab`: Open the link in a new tab.
                - `tab-bg`: Open the link in a new background tab.
                - `yank`: Yank the link to the clipboard.
                - `yank-primary`: Yank the link to the primary selection.
                - `fill`: Fill the commandline with the command given as
                          argument.
                - `cmd-tab`: Fill the commandline with `:open-tab` and the
                             link.
                - `cmd-tag-bg`: Fill the commandline with `:open-tab-bg` and
                                the link.
                - `rapid`: Open the link in a new tab and stay in hinting mode.
                - `download`: Download the link.
                - `userscript`: Call an userscript with `$QUTE_URL` set to the
                                link.
                - `spawn`: Spawn a command.

            *args: Arguments for spawn/userscript/fill.

                - With `spawn`: The executable and arguments to spawn.
                                `{hint-url}` will get replaced by the selected
                                URL.
                - With `userscript`: The userscript to execute.
                - With `fill`: The command to fill the statusbar with.
                                `{hint-url}` will get replaced by the selected
                                URL.
        """
        widget = self._tabs.currentWidget()
        frame = widget.page().mainFrame()
        if frame is None:
            raise cmdexc.CommandError("No frame focused!")
        try:
            group_enum = webelem.Group[group.replace('-', '_')]
        except KeyError:
            raise cmdexc.CommandError("Unknown hinting group {}!".format(
                group))
        try:
            target_enum = hints.Target[target.replace('-', '_')]
        except KeyError:
            raise cmdexc.CommandError("Unknown hinting target {}!".format(
                target))
        widget.hintmanager.start(frame, self._tabs.current_url(), group_enum,
                                 target_enum, *args)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def follow_hint(self):
        """Follow the currently selected hint."""
        self._tabs.currentWidget().hintmanager.follow_hint()

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def prev_page(self):
        """Open a "previous" link.

        This tries to automaticall click on typical "Previous Page" links using
        some heuristics.
        """
        self._prevnext(prev=True, newtab=False)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def next_page(self):
        """Open a "next" link.

        This tries to automatically click on typical "Next Page" links using
        some heuristics.
        """
        self._prevnext(prev=False, newtab=False)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def prev_page_tab(self):
        """Open a "previous" link in a new tab.

        This tries to automatically click on typical "Previous Page" links
        using some heuristics.
        """
        self._prevnext(prev=True, newtab=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def next_page_tab(self):
        """Open a "next" link in a new tab.

        This tries to automatically click on typical "Previous Page" links
        using some heuristics.
        """
        self._prevnext(prev=False, newtab=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def scroll(self, dx, dy, count=1):
        """Scroll the current tab by 'count * dx/dy'.

        Args:
            dx: How much to scroll in x-direction.
            dy: How much to scroll in x-direction.
            count: multiplier
        """
        dx = int(int(count) * float(dx))
        dy = int(int(count) * float(dy))
        cmdutils.check_overflow(dx, 'int')
        cmdutils.check_overflow(dy, 'int')
        self._tabs.currentWidget().page().currentFrame().scroll(dx, dy)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def scroll_perc_x(self, perc=None, count=None):
        """Scroll horizontally to a specific percentage of the page.

        The percentage can be given either as argument or as count.
        If no percentage is given, the page is scrolled to the end.

        Args:
            perc: Percentage to scroll.
            count: Percentage to scroll.
        """
        self._scroll_percent(perc, count, Qt.Horizontal)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def scroll_perc_y(self, perc=None, count=None):
        """Scroll vertically to a specific percentage of the page.

        The percentage can be given either as argument or as count.
        If no percentage is given, the page is scrolled to the end.

        Args:
            perc: Percentage to scroll.
            count: Percentage to scroll.
        """
        self._scroll_percent(perc, count, Qt.Vertical)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def scroll_page(self, x, y, count=1):
        """Scroll the frame page-wise.

        Args:
            x: How many pages to scroll to the right.
            y: How many pages to scroll down.
            count: multiplier
        """
        frame = self._tabs.currentWidget().page().currentFrame()
        size = frame.geometry()
        dx = int(count) * float(x) * size.width()
        dy = int(count) * float(y) * size.height()
        cmdutils.check_overflow(dx, 'int')
        cmdutils.check_overflow(dy, 'int')
        frame.scroll(dx, dy)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def yank(self, sel=False):
        """Yank the current URL to the clipboard or primary selection.

        Args:
            sel: True to use primary selection, False to use clipboard
        """
        clipboard = QApplication.clipboard()
        urlstr = self._tabs.current_url().toString(
            QUrl.FullyEncoded | QUrl.RemovePassword)
        if sel and clipboard.supportsSelection():
            mode = QClipboard.Selection
            target = "primary selection"
        else:
            mode = QClipboard.Clipboard
            target = "clipboard"
        log.misc.debug("Yanking to {}: '{}'".format(target, urlstr))
        clipboard.setText(urlstr, mode)
        message.info("URL yanked to {}".format(target))

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def yank_title(self, sel=False):
        """Yank the current title to the clipboard or primary selection.

        Args:
            sel: True to use primary selection, False to use clipboard
        """
        clipboard = QApplication.clipboard()
        title = self._tabs.tabText(self._tabs.currentIndex())
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        if sel and clipboard.supportsSelection():
            mode = QClipboard.Selection
            target = "primary selection"
        else:
            mode = QClipboard.Clipboard
            target = "clipboard"
        log.misc.debug("Yanking to {}: '{}'".format(target, title))
        clipboard.setText(title, mode)
        message.info("Title yanked to {}".format(target))

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def zoom_in(self, count=1):
        """Increase the zoom level for the current tab.

        Args:
            count: How many steps to zoom in.
        """
        tab = self._tabs.currentWidget()
        tab.zoom(count)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def zoom_out(self, count=1):
        """Decrease the zoom level for the current tab.

        Args:
            count: How many steps to zoom out.
        """
        tab = self._tabs.currentWidget()
        tab.zoom(-count)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
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
        tab = self._tabs.currentWidget()
        tab.zoom_perc(level)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_only(self):
        """Close all tabs except for the current one."""
        for tab in self._tabs.widgets:
            if tab is self._tabs.currentWidget():
                continue
            self._tabs.close_tab(tab)

    @cmdutils.register(instance='mainwindow.tabs.cmd', split=False)
    def open_tab(self, urlstr):
        """Open a new tab with a given url."""
        try:
            url = urlutils.fuzzy_url(urlstr)
        except urlutils.FuzzyUrlError as e:
            raise cmdexc.CommandError(e)
        self._tabs.tabopen(url, background=False, explicit=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd', split=False)
    def open_tab_bg(self, urlstr):
        """Open a new tab in background."""
        try:
            url = urlutils.fuzzy_url(urlstr)
        except urlutils.FuzzyUrlError as e:
            raise cmdexc.CommandError(e)
        self._tabs.tabopen(url, background=True, explicit=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def undo(self):
        """Re-open a closed tab (optionally skipping [count] closed tabs)."""
        if self._tabs.url_stack:
            self._tabs.tabopen(self._tabs.url_stack.pop())
        else:
            raise cmdexc.CommandError("Nothing to undo!")

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_prev(self, count=1):
        """Switch to the previous tab, or switch [count] tabs back.

        Args:
            count: How many tabs to switch back.
        """
        newidx = self._tabs.currentIndex() - count
        if newidx >= 0:
            self._tabs.setCurrentIndex(newidx)
        elif config.get('tabs', 'wrap'):
            self._tabs.setCurrentIndex(newidx % self._tabs.count())
        else:
            raise cmdexc.CommandError("First tab")

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_next(self, count=1):
        """Switch to the next tab, or switch [count] tabs forward.

        Args:
            count: How many tabs to switch forward.
        """
        newidx = self._tabs.currentIndex() + count
        if newidx < self._tabs.count():
            self._tabs.setCurrentIndex(newidx)
        elif config.get('tabs', 'wrap'):
            self._tabs.setCurrentIndex(newidx % self._tabs.count())
        else:
            raise cmdexc.CommandError("Last tab")

    @cmdutils.register(instance='mainwindow.tabs.cmd', nargs=(0, 1))
    def paste(self, sel=False, tab=False):
        """Open a page from the clipboard.

        Args:
            sel: True to use primary selection, False to use clipboard
            tab: True to open in a new tab.
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
        if tab:
            self._tabs.tabopen(url, explicit=True)
        else:
            widget = self._tabs.currentWidget()
            widget.openurl(url)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def paste_tab(self, sel=False):
        """Open a page from the clipboard in a new tab.

        Args:
            sel: True to use primary selection, False to use clipboard
        """
        self.paste(sel, True)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_focus(self, index=None, count=None):
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
                                        countzero=self._tabs.count())
        except ValueError as e:
            raise cmdexc.CommandError(e)
        cmdutils.check_overflow(idx + 1, 'int')
        if 1 <= idx <= self._tabs.count():
            self._tabs.setCurrentIndex(idx - 1)
        else:
            raise cmdexc.CommandError("There's no tab with index {}!".format(
                idx))

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_move(self, direction=None, count=None):
        """Move the current tab.

        Args:
            direction: + or - for relative moving, none for absolute.
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
        if not 0 <= new_idx < self._tabs.count():
            raise cmdexc.CommandError("Can't move tab to position {}!".format(
                new_idx))
        tab = self._tabs.currentWidget()
        cur_idx = self._tabs.currentIndex()
        icon = self._tabs.tabIcon(cur_idx)
        label = self._tabs.tabText(cur_idx)
        cmdutils.check_overflow(cur_idx, 'int')
        cmdutils.check_overflow(new_idx, 'int')
        self._tabs.setUpdatesEnabled(False)
        try:
            self._tabs.removeTab(cur_idx)
            self._tabs.insertTab(new_idx, tab, icon, label)
            self._tabs.setCurrentIndex(new_idx)
        finally:
            self._tabs.setUpdatesEnabled(True)

    @cmdutils.register(instance='mainwindow.tabs.cmd', split=False)
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

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def home(self):
        """Open main startpage in current tab."""
        self.openurl(config.get('general', 'startpage')[0])

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def run_userscript(self, cmd, *args):
        """Run an userscript given as argument.

        Args:
            cmd: The userscript to run.
            args: Arguments to pass to the userscript.
        """
        url = self._tabs.current_url()
        userscripts.run(cmd, *args, url=url)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def quickmark_save(self):
        """Save the current page as a quickmark."""
        quickmarks.prompt_save(self._tabs.current_url())

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def quickmark_load(self, name):
        """Load a quickmark."""
        urlstr = quickmarks.get(name)
        url = QUrl(urlstr)
        if not url.isValid():
            raise cmdexc.CommandError("Invalid URL {} ({})".format(
                urlstr, url.errorString()))
        self._tabs.currentWidget().openurl(url)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def quickmark_load_tab(self, name):
        """Load a quickmark in a new tab."""
        url = quickmarks.get(name)
        self._tabs.tabopen(url, background=False, explicit=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def quickmark_load_tab_bg(self, name):
        """Load a quickmark in a new background tab."""
        url = quickmarks.get(name)
        self._tabs.tabopen(url, background=True, explicit=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd', name='inspector')
    def toggle_inspector(self):
        """Toggle the web inspector."""
        cur = self._tabs.currentWidget()
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

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def download_page(self):
        """Download the current page."""
        page = self._tabs.currentWidget().page()
        self._tabs.download_get.emit(self._tabs.current_url(), page)

    @cmdutils.register(instance='mainwindow.tabs.cmd',
                       modes=[usertypes.KeyMode.insert],
                       hide=True)
    def open_editor(self):
        """Open an external editor with the currently selected form field.

        The editor which should be launched can be configured via the
        `general -> editor` config option.

        //

        We use QProcess rather than subprocess here because it makes it a lot
        easier to execute some code as soon as the process has been finished
        and do everything async.
        """
        frame = self._tabs.currentWidget().page().currentFrame()
        elem = webelem.focus_elem(frame)
        if elem.isNull():
            raise cmdexc.CommandError("No element focused!")
        if not webelem.is_editable(elem, strict=True):
            raise cmdexc.CommandError("Focused element is not editable!")
        if webelem.is_content_editable(elem):
            text = elem.toPlainText()
        else:
            text = elem.evaluateJavaScript('this.value')
        self._editor = editor.ExternalEditor(self._tabs)
        self._editor.editing_finished.connect(
            partial(self.on_editing_finished, elem))
        self._editor.edit(text)

    def on_editing_finished(self, elem, text):
        """Write the editor text into the form field and clean up tempfile.

        Callback for QProcess when the editor was closed.

        Args:
            elem: The QWebElement which was modified.
            text: The new text to insert.
        """
        if elem.isNull():
            raise cmdexc.CommandError("Element vanished while editing!")
        if webelem.is_content_editable(elem):
            log.misc.debug("Filling element {} via setPlainText.".format(
                webelem.debug_text(elem)))
            elem.setPlainText(text)
        else:
            log.misc.debug("Filling element {} via javascript.".format(
                webelem.debug_text(elem)))
            text = webelem.javascript_escape(text)
            elem.evaluateJavaScript("this.value='{}'".format(text))
