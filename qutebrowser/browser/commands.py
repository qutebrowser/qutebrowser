# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et

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
from PyQt5.QtCore import pyqtSignal, Qt, QUrl
from PyQt5.QtGui import QClipboard
from PyQt5.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebInspector

import qutebrowser.commands.utils as cmdutils
import qutebrowser.config.config as config
import qutebrowser.browser.hints as hints
import qutebrowser.utils.message as message
import qutebrowser.utils.webelem as webelem
import qutebrowser.browser.quickmarks as quickmarks
import qutebrowser.utils.log as log
import qutebrowser.utils.url as urlutils
from qutebrowser.utils.misc import shell_escape
from qutebrowser.utils.qt import (check_overflow, check_print_compat,
                                  qt_ensure_valid, QtValueError)
from qutebrowser.utils.editor import ExternalEditor
from qutebrowser.commands.exceptions import CommandError
from qutebrowser.commands.userscripts import UserscriptRunner


class CommandDispatcher:

    """Command dispatcher for TabbedBrowser.

    Contains all commands which are related to the current tab.

    We can't simply add these commands to BrowserTab directly and use
    currentWidget() for TabbedBrowser.cmd because at the time
    cmdutils.register() decorators are run, currentWidget() will return None.

    Attributes:
        _tabs: The TabbedBrowser object.
        _editor: The ExternalEditor object.
        _userscript_runners: A list of userscript runners.

    Signals:
        start_download: When a download should be started.
                        arg: What to download, as QUrl.
    """

    start_download = pyqtSignal('QUrl')

    def __init__(self, parent):
        """Constructor.

        Args:
            parent: The TabbedBrowser for this dispatcher.
        """
        self._userscript_runners = []
        self._tabs = parent
        self._editor = None

    def _current_url(self):
        """Get the URL of the current tab."""
        url = self._tabs.currentWidget().url()
        try:
            qt_ensure_valid(url)
        except QtValueError as e:
            msg = "Current URL is invalid"
            if e.reason:
                msg += " ({})".format(e.reason)
            msg += "!"
            raise CommandError(msg)
        return url

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
        perc = check_overflow(perc, 'int', fatal=False)
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
            raise CommandError("No frame focused!")
        widget.hintmanager.follow_prevnext(frame, self._current_url(), prev,
                                           newtab)

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
            raise ValueError
        if direction == '-':
            return self._tabs.currentIndex() - delta
        elif direction == '+':
            return self._tabs.currentIndex() + delta

    def _editor_cleanup(self, oshandle, filename):
        """Clean up temporary file when the editor was closed."""
        os.close(oshandle)
        try:
            os.remove(filename)
        except PermissionError:
            raise CommandError("Failed to delete tempfile...")

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
            raise CommandError(e)
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
        if not check_print_compat():
            raise CommandError("Printing on Qt < 5.3.0 on Windows is broken, "
                               "please upgrade!")
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
        if not check_print_compat():
            raise CommandError("Printing on Qt < 5.3.0 on Windows is broken, "
                               "please upgrade!")
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
    def hint(self, groupstr='all', targetstr='normal'):
        """Start hinting.

        Args:
            groupstr: The hinting mode to use.
            targetstr: Where to open the links.
        """
        widget = self._tabs.currentWidget()
        frame = widget.page().mainFrame()
        if frame is None:
            raise CommandError("No frame focused!")
        try:
            group = getattr(webelem.Group, groupstr.replace('-', '_'))
        except AttributeError:
            raise CommandError("Unknown hinting group {}!".format(groupstr))
        try:
            target = getattr(hints.Target, targetstr.replace('-', '_'))
        except AttributeError:
            raise CommandError("Unknown hinting target {}!".format(targetstr))
        widget.hintmanager.start(frame, self._current_url(), group, target)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def follow_hint(self):
        """Follow the currently selected hint."""
        self._tabs.currentWidget().hintmanager.follow_hint()

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def prev_page(self):
        """Open a "previous" link."""
        self._prevnext(prev=True, newtab=False)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def next_page(self):
        """Open a "next" link."""
        self._prevnext(prev=False, newtab=False)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def prev_page_tab(self):
        """Open a "previous" link in a new tab."""
        self._prevnext(prev=True, newtab=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def next_page_tab(self):
        """Open a "next" link in a new tab."""
        self._prevnext(prev=False, newtab=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def scroll(self, dx, dy, count=1):
        """Scroll the current tab by count * dx/dy.

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
        """Scroll the current tab to a specific percent of the page (horiz).

        Args:
            perc: Percentage to scroll.
            count: Percentage to scroll.
        """
        self._scroll_percent(perc, count, Qt.Horizontal)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def scroll_perc_y(self, perc=None, count=None):
        """Scroll the current tab to a specific percent of the page (vert).

        Args:
            perc: Percentage to scroll.
            count: Percentage to scroll.
        """
        self._scroll_percent(perc, count, Qt.Vertical)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def scroll_page(self, mx, my, count=1):
        """Scroll the frame page-wise.

        Args:
            mx: How many pages to scroll to the right.
            my: How many pages to scroll down.
            count: multiplier
        """
        frame = self._tabs.currentWidget().page().currentFrame()
        size = frame.geometry()
        dx = int(count) * float(mx) * size.width()
        dy = int(count) * float(my) * size.height()
        cmdutils.check_overflow(dx, 'int')
        cmdutils.check_overflow(dy, 'int')
        frame.scroll(dx, dy)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def yank(self, sel=False):
        """Yank the current URL to the clipboard or primary selection.

        Args:
            sel: True to use primary selection, False to use clipboard
        """
        urlstr = self._current_url().toString(QUrl.FullyEncoded |
                                              QUrl.RemovePassword)
        if sel:
            mode = QClipboard.Selection
            target = "primary selection"
        else:
            mode = QClipboard.Clipboard
            target = "clipboard"
        log.misc.debug("Yanking to {}: '{}'".format(target, urlstr))
        QApplication.clipboard().setText(urlstr, mode)
        message.info("URL yanked to {}".format(target))

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def yank_title(self, sel=False):
        """Yank the current title to the clipboard or primary selection.

        Args:
            sel: True to use primary selection, False to use clipboard
        """
        title = self._tabs.tabText(self._tabs.currentIndex())
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        if sel:
            mode = QClipboard.Selection
            target = "primary selection"
        else:
            mode = QClipboard.Clipboard
            target = "clipboard"
        log.misc.debug("Yanking to {}: '{}'".format(target, title))
        QApplication.clipboard().setText(title, mode)
        message.info("Title yanked to {}".format(target))

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def zoom_in(self, count=1):
        """Increase the zoom level for the current tab.

        Args:
            count: How many steps to take.
        """
        tab = self._tabs.currentWidget()
        tab.zoom(count)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def zoom_out(self, count=1):
        """Decrease the zoom level for the current tab.

        Args:
            count: How many steps to take.
        """
        tab = self._tabs.currentWidget()
        tab.zoom(-count)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def zoom(self, zoom=None, count=None):
        """Set the zoom level for the current tab to [count] or 100 percent.

        Args:
            count: How many steps to take.
        """
        try:
            level = cmdutils.arg_or_count(zoom, count, default=100)
        except ValueError as e:
            raise CommandError(e)
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
            raise CommandError(e)
        self._tabs.tabopen(url, background=False)

    @cmdutils.register(instance='mainwindow.tabs.cmd', split=False)
    def open_tab_bg(self, urlstr):
        """Open a new tab in background."""
        try:
            url = urlutils.fuzzy_url(urlstr)
        except urlutils.FuzzyUrlError as e:
            raise CommandError(e)
        self._tabs.tabopen(url, background=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def open_tab_cur(self):
        """Set the statusbar to :tabopen and the current URL."""
        urlstr = self._current_url().toDisplayString(QUrl.FullyEncoded)
        message.set_cmd_text(':open-tab ' + urlstr)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def open_cur(self):
        """Set the statusbar to :open and the current URL."""
        urlstr = self._current_url().toDisplayString(QUrl.FullyEncoded)
        message.set_cmd_text(':open ' + urlstr)

    @cmdutils.register(instance='mainwindow.tabs.cmd', hide=True)
    def open_tab_bg_cur(self):
        """Set the statusbar to :tabopen-bg and the current URL."""
        urlstr = self._current_url().toDisplayString(QUrl.FullyEncoded)
        message.set_cmd_text(':open-tab-bg ' + urlstr)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def undo(self):
        """Re-open a closed tab (optionally skipping [count] tabs)."""
        if self._tabs.url_stack:
            self._tabs.tabopen(self._tabs.url_stack.pop())
        else:
            raise CommandError("Nothing to undo!")

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_prev(self, count=1):
        """Switch to the previous tab, or skip [count] tabs.

        Args:
            count: How many tabs to switch back.
        """
        newidx = self._tabs.currentIndex() - count
        if newidx >= 0:
            self._tabs.setCurrentIndex(newidx)
        elif config.get('tabbar', 'wrap'):
            self._tabs.setCurrentIndex(newidx % self._tabs.count())
        else:
            raise CommandError("First tab")

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_next(self, count=1):
        """Switch to the next tab, or skip [count] tabs.

        Args:
            count: How many tabs to switch forward.
        """
        newidx = self._tabs.currentIndex() + count
        if newidx < self._tabs.count():
            self._tabs.setCurrentIndex(newidx)
        elif config.get('tabbar', 'wrap'):
            self._tabs.setCurrentIndex(newidx % self._tabs.count())
        else:
            raise CommandError("Last tab")

    @cmdutils.register(instance='mainwindow.tabs.cmd', nargs=(0, 1))
    def paste(self, sel=False, tab=False):
        """Open a page from the clipboard.

        Args:
            sel: True to use primary selection, False to use clipboard
            tab: True to open in a new tab.
        """
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        text = QApplication.clipboard().text(mode)
        if not text:
            raise CommandError("Clipboard is empty.")
        log.misc.debug("Clipboard contained: '{}'".format(text))
        try:
            url = urlutils.fuzzy_url(text)
        except urlutils.FuzzyUrlError as e:
            raise CommandError(e)
        if tab:
            self._tabs.tabopen(url)
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
            index: The tab index to focus, starting with 1.
        """
        try:
            idx = cmdutils.arg_or_count(index, count, default=1,
                                        countzero=self._tabs.count())
        except ValueError as e:
            raise CommandError(e)
        cmdutils.check_overflow(idx + 1, 'int')
        if 1 <= idx <= self._tabs.count():
            self._tabs.setCurrentIndex(idx - 1)
        else:
            raise CommandError("There's no tab with index {}!".format(idx))

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_move(self, direction=None, count=None):
        """Move the current tab.

        Args:
            direction: + or - for relative moving, None for absolute.
            count: If moving absolutely: New position (or first).
                   If moving relatively: Offset.
        """
        if direction is None:
            new_idx = self._tab_move_absolute(count)
        elif direction in '+-':
            try:
                new_idx = self._tab_move_relative(direction, count)
            except ValueError:
                raise CommandError("Count must be given for relative moving!")
        else:
            raise CommandError("Invalid direction '{}'!".format(direction))
        if not 0 <= new_idx < self._tabs.count():
            raise CommandError("Can't move tab to position {}!".format(
                new_idx))
        tab = self._tabs.currentWidget()
        cur_idx = self._tabs.currentIndex()
        icon = self._tabs.tabIcon(cur_idx)
        label = self._tabs.tabText(cur_idx)
        cmdutils.check_overflow(cur_idx, 'int')
        cmdutils.check_overflow(new_idx, 'int')
        self._tabs.removeTab(cur_idx)
        self._tabs.insertTab(new_idx, tab, icon, label)
        self._tabs.setCurrentIndex(new_idx)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def tab_focus_last(self):
        """Select the tab which was last focused."""
        idx = self._tabs.indexOf(self._tabs.last_focused)
        if idx == -1:
            raise CommandError("Last focused tab vanished!")
        self._tabs.setCurrentIndex(idx)

    @cmdutils.register(instance='mainwindow.tabs.cmd', split=False)
    def spawn(self, cmd):
        """Spawn a command in a shell. {} gets replaced by the current URL.

        The URL will already be quoted correctly, so there's no need to do
        that.

        The command will be run in a shell, so you can use shell features like
        redirections.

        We use subprocess rather than Qt's QProcess here because of it's
        shell=True argument and because we really don't care about the process
        anymore as soon as it's spawned.

        Args:
            cmd: The command to execute.
        """
        urlstr = self._current_url().toString(QUrl.FullyEncoded |
                                              QUrl.RemovePassword)
        cmd = cmd.replace('{}', shell_escape(urlstr))
        log.procs.debug("Executing: {}".format(cmd))
        subprocess.Popen(cmd, shell=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def home(self):
        """Open main startpage in current tab."""
        self.openurl(config.get('general', 'startpage')[0])

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def run_userscript(self, cmd, *args):
        """Run an userscript given as argument."""
        # We don't remove the password in the URL here, as it's probably safe
        # to pass via env variable.
        urlstr = self._current_url().toString(QUrl.FullyEncoded)
        runner = UserscriptRunner(self._tabs)
        runner.got_cmd.connect(self._tabs.got_cmd)
        runner.run(cmd, *args, env={'QUTE_URL': urlstr})
        self._userscript_runners.append(runner)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def quickmark_save(self):
        """Save the current page as a quickmark."""
        quickmarks.prompt_save(self._current_url())

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def quickmark_load(self, name):
        """Load a quickmark."""
        urlstr = quickmarks.get(name)
        url = QUrl(urlstr)
        if not url.isValid():
            raise CommandError("Invalid URL {} ({})".format(
                urlstr, url.errorString()))
        self._tabs.currentWidget().openurl(url)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def quickmark_load_tab(self, name):
        """Load a quickmark in a new tab."""
        url = quickmarks.get(name)
        self._tabs.tabopen(url, background=False)

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def quickmark_load_tab_bg(self, name):
        """Load a quickmark in a new background tab."""
        url = quickmarks.get(name)
        self._tabs.tabopen(url, background=True)

    @cmdutils.register(instance='mainwindow.tabs.cmd', name='inspector')
    def toggle_inspector(self):
        """Toggle the web inspector."""
        cur = self._tabs.currentWidget()
        if cur.inspector is None:
            if not config.get('general', 'developer-extras'):
                raise CommandError("Please enable developer-extras before "
                                   "using the webinspector!")
            cur.inspector = QWebInspector()
            cur.inspector.setPage(cur.page())
            cur.inspector.show()
        elif cur.inspector.isVisible():
            cur.inspector.hide()
        else:
            if not config.get('general', 'developer-extras'):
                raise CommandError("Please enable developer-extras before "
                                   "using the webinspector!")
            else:
                cur.inspector.show()

    @cmdutils.register(instance='mainwindow.tabs.cmd')
    def download_page(self):
        """Download the current page."""
        self.start_download.emit(self._current_url())

    @cmdutils.register(instance='mainwindow.tabs.cmd', modes=['insert'],
                       hide=True)
    def open_editor(self):
        """Open an external editor with the current form field.

        We use QProcess rather than subprocess here because it makes it a lot
        easier to execute some code as soon as the process has been finished
        and do everything async.
        """
        frame = self._tabs.currentWidget().page().currentFrame()
        elem = frame.findFirstElement(webelem.SELECTORS[
            webelem.Group.editable_focused])
        if elem.isNull():
            raise CommandError("No editable element focused!")
        text = elem.evaluateJavaScript('this.value')
        self._editor = ExternalEditor(self._tabs)
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
            raise CommandError("Element vanished while editing!")
        text = webelem.javascript_escape(text)
        elem.evaluateJavaScript("this.value='{}'".format(text))
