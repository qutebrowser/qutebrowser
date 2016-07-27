# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Wrapper over our (QtWebKit) WebView."""

import sys
import functools
import xml.etree.ElementTree

from PyQt5.QtCore import pyqtSlot, Qt, QEvent, QUrl, QPoint, QTimer
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWebKitWidgets import QWebPage, QWebFrame
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtPrintSupport import QPrinter

from qutebrowser.browser import browsertab
from qutebrowser.browser.webkit import webview, tabhistory
from qutebrowser.utils import qtutils, objreg, usertypes, utils


class WebKitPrinting(browsertab.AbstractPrinting):

    """QtWebKit implementations related to printing."""

    def _do_check(self):
        if not qtutils.check_print_compat():
            # WORKAROUND (remove this when we bump the requirements to 5.3.0)
            raise browsertab.WebTabError(
                "Printing on Qt < 5.3.0 on Windows is broken, please upgrade!")

    def check_pdf_support(self):
        self._do_check()

    def check_printer_support(self):
        self._do_check()

    def to_pdf(self, filename):
        printer = QPrinter()
        printer.setOutputFileName(filename)
        self.to_printer(printer)

    def to_printer(self, printer):
        self._widget.print(printer)


class WebKitSearch(browsertab.AbstractSearch):

    """QtWebKit implementations related to searching on the page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flags = QWebPage.FindFlags(0)

    def _call_cb(self, callback, found):
        """Call the given callback if it's non-None.

        Delays the call via a QTimer so the website is re-rendered in between.

        Args:
            callback: What to call
            found: If the text was found
        """
        if callback is not None:
            QTimer.singleShot(0, functools.partial(callback, found))

    def clear(self):
        # We first clear the marked text, then the highlights
        self._widget.findText('')
        self._widget.findText('', QWebPage.HighlightAllOccurrences)

    def search(self, text, *, ignore_case=False, reverse=False,
               result_cb=None):
        flags = QWebPage.FindWrapsAroundDocument
        if ignore_case == 'smart':
            if not text.islower():
                flags |= QWebPage.FindCaseSensitively
        elif not ignore_case:
            flags |= QWebPage.FindCaseSensitively
        if reverse:
            flags |= QWebPage.FindBackward
        # We actually search *twice* - once to highlight everything, then again
        # to get a mark so we can navigate.
        found = self._widget.findText(text, flags)
        self._widget.findText(text, flags | QWebPage.HighlightAllOccurrences)
        self.text = text
        self._flags = flags
        self._call_cb(result_cb, found)

    def next_result(self, *, result_cb=None):
        found = self._widget.findText(self.text, self._flags)
        self._call_cb(result_cb, found)

    def prev_result(self, *, result_cb=None):
        # The int() here makes sure we get a copy of the flags.
        flags = QWebPage.FindFlags(int(self._flags))
        if flags & QWebPage.FindBackward:
            flags &= ~QWebPage.FindBackward
        else:
            flags |= QWebPage.FindBackward
        found = self._widget.findText(self.text, flags)
        self._call_cb(result_cb, found)


class WebKitCaret(browsertab.AbstractCaret):

    """QtWebKit implementations related to moving the cursor/selection."""

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_entered(self, mode):
        if mode != usertypes.KeyMode.caret:
            return

        settings = self._widget.settings()
        settings.setAttribute(QWebSettings.CaretBrowsingEnabled, True)
        self.selection_enabled = bool(self.selection())

        if self._widget.isVisible():
            # Sometimes the caret isn't immediately visible, but unfocusing
            # and refocusing it fixes that.
            self._widget.clearFocus()
            self._widget.setFocus(Qt.OtherFocusReason)

            # Move the caret to the first element in the viewport if there
            # isn't any text which is already selected.
            #
            # Note: We can't use hasSelection() here, as that's always
            # true in caret mode.
            if not self.selection():
                self._widget.page().currentFrame().evaluateJavaScript(
                    utils.read_file('javascript/position_caret.js'))

    @pyqtSlot()
    def _on_mode_left(self):
        settings = self._widget.settings()
        if settings.testAttribute(QWebSettings.CaretBrowsingEnabled):
            if self.selection_enabled and self._widget.hasSelection():
                # Remove selection if it exists
                self._widget.triggerPageAction(QWebPage.MoveToNextChar)
            settings.setAttribute(QWebSettings.CaretBrowsingEnabled, False)
            self.selection_enabled = False

    def move_to_next_line(self, count=1):
        if not self.selection_enabled:
            act = QWebPage.MoveToNextLine
        else:
            act = QWebPage.SelectNextLine
        for _ in range(count):
            self._widget.triggerPageAction(act)

    def move_to_prev_line(self, count=1):
        if not self.selection_enabled:
            act = QWebPage.MoveToPreviousLine
        else:
            act = QWebPage.SelectPreviousLine
        for _ in range(count):
            self._widget.triggerPageAction(act)

    def move_to_next_char(self, count=1):
        if not self.selection_enabled:
            act = QWebPage.MoveToNextChar
        else:
            act = QWebPage.SelectNextChar
        for _ in range(count):
            self._widget.triggerPageAction(act)

    def move_to_prev_char(self, count=1):
        if not self.selection_enabled:
            act = QWebPage.MoveToPreviousChar
        else:
            act = QWebPage.SelectPreviousChar
        for _ in range(count):
            self._widget.triggerPageAction(act)

    def move_to_end_of_word(self, count=1):
        if not self.selection_enabled:
            act = [QWebPage.MoveToNextWord]
            if sys.platform == 'win32':  # pragma: no cover
                act.append(QWebPage.MoveToPreviousChar)
        else:
            act = [QWebPage.SelectNextWord]
            if sys.platform == 'win32':  # pragma: no cover
                act.append(QWebPage.SelectPreviousChar)
        for _ in range(count):
            for a in act:
                self._widget.triggerPageAction(a)

    def move_to_next_word(self, count=1):
        if not self.selection_enabled:
            act = [QWebPage.MoveToNextWord]
            if sys.platform != 'win32':  # pragma: no branch
                act.append(QWebPage.MoveToNextChar)
        else:
            act = [QWebPage.SelectNextWord]
            if sys.platform != 'win32':  # pragma: no branch
                act.append(QWebPage.SelectNextChar)
        for _ in range(count):
            for a in act:
                self._widget.triggerPageAction(a)

    def move_to_prev_word(self, count=1):
        if not self.selection_enabled:
            act = QWebPage.MoveToPreviousWord
        else:
            act = QWebPage.SelectPreviousWord
        for _ in range(count):
            self._widget.triggerPageAction(act)

    def move_to_start_of_line(self):
        if not self.selection_enabled:
            act = QWebPage.MoveToStartOfLine
        else:
            act = QWebPage.SelectStartOfLine
        self._widget.triggerPageAction(act)

    def move_to_end_of_line(self):
        if not self.selection_enabled:
            act = QWebPage.MoveToEndOfLine
        else:
            act = QWebPage.SelectEndOfLine
        self._widget.triggerPageAction(act)

    def move_to_start_of_next_block(self, count=1):
        if not self.selection_enabled:
            act = [QWebPage.MoveToNextLine,
                   QWebPage.MoveToStartOfBlock]
        else:
            act = [QWebPage.SelectNextLine,
                   QWebPage.SelectStartOfBlock]
        for _ in range(count):
            for a in act:
                self._widget.triggerPageAction(a)

    def move_to_start_of_prev_block(self, count=1):
        if not self.selection_enabled:
            act = [QWebPage.MoveToPreviousLine,
                   QWebPage.MoveToStartOfBlock]
        else:
            act = [QWebPage.SelectPreviousLine,
                   QWebPage.SelectStartOfBlock]
        for _ in range(count):
            for a in act:
                self._widget.triggerPageAction(a)

    def move_to_end_of_next_block(self, count=1):
        if not self.selection_enabled:
            act = [QWebPage.MoveToNextLine,
                   QWebPage.MoveToEndOfBlock]
        else:
            act = [QWebPage.SelectNextLine,
                   QWebPage.SelectEndOfBlock]
        for _ in range(count):
            for a in act:
                self._widget.triggerPageAction(a)

    def move_to_end_of_prev_block(self, count=1):
        if not self.selection_enabled:
            act = [QWebPage.MoveToPreviousLine, QWebPage.MoveToEndOfBlock]
        else:
            act = [QWebPage.SelectPreviousLine, QWebPage.SelectEndOfBlock]
        for _ in range(count):
            for a in act:
                self._widget.triggerPageAction(a)

    def move_to_start_of_document(self):
        if not self.selection_enabled:
            act = QWebPage.MoveToStartOfDocument
        else:
            act = QWebPage.SelectStartOfDocument
        self._widget.triggerPageAction(act)

    def move_to_end_of_document(self):
        if not self.selection_enabled:
            act = QWebPage.MoveToEndOfDocument
        else:
            act = QWebPage.SelectEndOfDocument
        self._widget.triggerPageAction(act)

    def toggle_selection(self):
        self.selection_enabled = not self.selection_enabled
        mainwindow = objreg.get('main-window', scope='window',
                                window=self._win_id)
        mainwindow.status.set_mode_active(usertypes.KeyMode.caret, True)

    def drop_selection(self):
        self._widget.triggerPageAction(QWebPage.MoveToNextChar)

    def has_selection(self):
        return self._widget.hasSelection()

    def selection(self, html=False):
        if html:
            return self._widget.selectedHtml()
        return self._widget.selectedText()

    def follow_selected(self, *, tab=False):
        if not self.has_selection():
            return
        if QWebSettings.globalSettings().testAttribute(
                QWebSettings.JavascriptEnabled):
            if tab:
                self._widget.page().open_target = usertypes.ClickTarget.tab
            self._tab.run_js_async(
                'window.getSelection().anchorNode.parentNode.click()')
        else:
            selection = self.selection(html=True)
            try:
                selected_element = xml.etree.ElementTree.fromstring(
                    '<html>{}</html>'.format(selection)).find('a')
            except xml.etree.ElementTree.ParseError:
                raise browsertab.WebTabError('Could not parse selected '
                                             'element!')

            if selected_element is not None:
                try:
                    url = selected_element.attrib['href']
                except KeyError:
                    raise browsertab.WebTabError('Anchor element without '
                                                 'href!')
                url = self._tab.url().resolved(QUrl(url))
                if tab:
                    self._tab.new_tab_requested.emit(url)
                else:
                    self._tab.openurl(url)


class WebKitZoom(browsertab.AbstractZoom):

    """QtWebKit implementations related to zooming."""

    def _set_factor_internal(self, factor):
        self._widget.setZoomFactor(factor)

    def factor(self):
        return self._widget.zoomFactor()


class WebKitScroller(browsertab.AbstractScroller):

    """QtWebKit implementations related to scrolling."""

    # FIXME:qtwebengine When to use the main frame, when the current one?

    def pos_px(self):
        return self._widget.page().mainFrame().scrollPosition()

    def pos_perc(self):
        return self._widget.scroll_pos

    def to_point(self, point):
        self._widget.page().mainFrame().setScrollPosition(point)

    def delta(self, x=0, y=0):
        qtutils.check_overflow(x, 'int')
        qtutils.check_overflow(y, 'int')
        self._widget.page().mainFrame().scroll(x, y)

    def delta_page(self, x=0.0, y=0.0):
        if y.is_integer():
            y = int(y)
            if y == 0:
                pass
            elif y < 0:
                self.page_up(count=-y)
            elif y > 0:
                self.page_down(count=y)
            y = 0
        if x == 0 and y == 0:
            return
        size = self._widget.page().mainFrame().geometry()
        self.delta(x * size.width(), y * size.height())

    def to_perc(self, x=None, y=None):
        if x is None and y == 0:
            self.top()
        elif x is None and y == 100:
            self.bottom()
        else:
            for val, orientation in [(x, Qt.Horizontal), (y, Qt.Vertical)]:
                if val is not None:
                    val = qtutils.check_overflow(val, 'int', fatal=False)
                    frame = self._widget.page().mainFrame()
                    m = frame.scrollBarMaximum(orientation)
                    if m == 0:
                        continue
                    frame.setScrollBarValue(orientation, int(m * val / 100))

    def _key_press(self, key, count=1, getter_name=None, direction=None):
        frame = self._widget.page().mainFrame()
        press_evt = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, 0, 0, 0)
        release_evt = QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier, 0, 0, 0)
        getter = None if getter_name is None else getattr(frame, getter_name)

        # FIXME:qtwebengine needed?
        # self._widget.setFocus()

        for _ in range(count):
            # Abort scrolling if the minimum/maximum was reached.
            if (getter is not None and
                    frame.scrollBarValue(direction) == getter(direction)):
                return
            self._widget.keyPressEvent(press_evt)
            self._widget.keyReleaseEvent(release_evt)

    def up(self, count=1):
        self._key_press(Qt.Key_Up, count, 'scrollBarMinimum', Qt.Vertical)

    def down(self, count=1):
        self._key_press(Qt.Key_Down, count, 'scrollBarMaximum', Qt.Vertical)

    def left(self, count=1):
        self._key_press(Qt.Key_Left, count, 'scrollBarMinimum', Qt.Horizontal)

    def right(self, count=1):
        self._key_press(Qt.Key_Right, count, 'scrollBarMaximum', Qt.Horizontal)

    def top(self):
        self._key_press(Qt.Key_Home)

    def bottom(self):
        self._key_press(Qt.Key_End)

    def page_up(self, count=1):
        self._key_press(Qt.Key_PageUp, count, 'scrollBarMinimum', Qt.Vertical)

    def page_down(self, count=1):
        self._key_press(Qt.Key_PageDown, count, 'scrollBarMaximum',
                        Qt.Vertical)

    def at_top(self):
        return self.pos_px().y() == 0

    def at_bottom(self):
        frame = self._widget.page().currentFrame()
        return self.pos_px().y() >= frame.scrollBarMaximum(Qt.Vertical)


class WebKitHistory(browsertab.AbstractHistory):

    """QtWebKit implementations related to page history."""

    def current_idx(self):
        return self._history.currentItemIndex()

    def back(self):
        self._history.back()

    def forward(self):
        self._history.forward()

    def can_go_back(self):
        return self._history.canGoBack()

    def can_go_forward(self):
        return self._history.canGoForward()

    def serialize(self):
        return qtutils.serialize(self._history)

    def deserialize(self, data):
        return qtutils.deserialize(data, self._history)

    def load_items(self, items):
        stream, _data, user_data = tabhistory.serialize(items)
        qtutils.deserialize_stream(stream, self._history)
        for i, data in enumerate(user_data):
            self._history.itemAt(i).setUserData(data)
        cur_data = self._history.currentItem().userData()
        if cur_data is not None:
            if 'zoom' in cur_data:
                self._tab.zoom.set_factor(cur_data['zoom'])
            if ('scroll-pos' in cur_data and
                    self._tab.scroller.pos_px() == QPoint(0, 0)):
                QTimer.singleShot(0, functools.partial(
                    self._tab.scroller.to_point, cur_data['scroll-pos']))


class WebKitTab(browsertab.AbstractTab):

    """A QtWebKit tab in the browser."""

    def __init__(self, win_id, mode_manager, parent=None):
        super().__init__(win_id)
        widget = webview.WebView(win_id, self.tab_id, tab=self)
        self.history = WebKitHistory(self)
        self.scroller = WebKitScroller(self, parent=self)
        self.caret = WebKitCaret(win_id=win_id, mode_manager=mode_manager,
                                 tab=self, parent=self)
        self.zoom = WebKitZoom(win_id=win_id, parent=self)
        self.search = WebKitSearch(parent=self)
        self.printing = WebKitPrinting()
        self._set_widget(widget)
        self._connect_signals()
        self.zoom.set_default()
        self.backend = usertypes.Backend.QtWebKit

    def openurl(self, url):
        self._openurl_prepare(url)
        self._widget.openurl(url)

    def url(self):
        return self._widget.url()

    def dump_async(self, callback, *, plain=False):
        frame = self._widget.page().mainFrame()
        if plain:
            callback(frame.toPlainText())
        else:
            callback(frame.toHtml())

    def run_js_async(self, code, callback=None):
        result = self.run_js_blocking(code)
        if callback is not None:
            callback(result)

    def run_js_blocking(self, code):
        return self._widget.page().mainFrame().evaluateJavaScript(code)

    def icon(self):
        return self._widget.icon()

    def shutdown(self):
        self._widget.shutdown()

    def reload(self, *, force=False):
        if force:
            action = QWebPage.ReloadAndBypassCache
        else:
            action = QWebPage.Reload
        self._widget.triggerPageAction(action)

    def stop(self):
        self._widget.stop()

    def title(self):
        return self._widget.title()

    def clear_ssl_errors(self):
        nam = self._widget.page().networkAccessManager()
        nam.clear_all_ssl_errors()

    def set_html(self, html, base_url):
        self._widget.setHtml(html, base_url)

    @pyqtSlot()
    def _on_frame_load_finished(self):
        """Make sure we emit an appropriate status when loading finished.

        While Qt has a bool "ok" attribute for loadFinished, it always is True
        when using error pages... See
        https://github.com/The-Compiler/qutebrowser/issues/84
        """
        self._on_load_finished(not self._widget.page().error_occurred)

    @pyqtSlot()
    def _on_webkit_icon_changed(self):
        """Emit iconChanged with a QIcon like QWebEngineView does."""
        self.icon_changed.emit(self._widget.icon())

    @pyqtSlot(QWebFrame)
    def _on_frame_created(self, frame):
        """Connect the contentsSizeChanged signal of each frame."""
        # FIXME:qtwebengine those could theoretically regress:
        # https://github.com/The-Compiler/qutebrowser/issues/152
        # https://github.com/The-Compiler/qutebrowser/issues/263
        frame.contentsSizeChanged.connect(self.contents_size_changed)

    def _connect_signals(self):
        view = self._widget
        page = view.page()
        frame = page.mainFrame()
        page.windowCloseRequested.connect(self.window_close_requested)
        page.linkHovered.connect(self.link_hovered)
        page.loadProgress.connect(self._on_load_progress)
        frame.loadStarted.connect(self._on_load_started)
        view.scroll_pos_changed.connect(self.scroller.perc_changed)
        view.titleChanged.connect(self.title_changed)
        view.urlChanged.connect(self._on_url_changed)
        view.shutting_down.connect(self.shutting_down)
        page.networkAccessManager().sslErrors.connect(self._on_ssl_errors)
        frame.loadFinished.connect(self._on_frame_load_finished)
        view.iconChanged.connect(self._on_webkit_icon_changed)
