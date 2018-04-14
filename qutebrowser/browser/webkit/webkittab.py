# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import re
import functools
import xml.etree.ElementTree

import pygments
import pygments.lexers
import pygments.formatters

import sip
from PyQt5.QtCore import (pyqtSlot, Qt, QEvent, QUrl, QPoint, QTimer, QSizeF,
                          QSize)
from PyQt5.QtGui import QKeyEvent, QIcon
from PyQt5.QtWebKitWidgets import QWebPage, QWebFrame
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtPrintSupport import QPrinter

from qutebrowser.browser import browsertab, shared
from qutebrowser.browser.webkit import (webview, tabhistory, webkitelem,
                                        webkitsettings)
from qutebrowser.utils import qtutils, objreg, usertypes, utils, log, debug


class WebKitAction(browsertab.AbstractAction):

    """QtWebKit implementations related to web actions."""

    action_class = QWebPage
    action_base = QWebPage.WebAction

    def exit_fullscreen(self):
        raise browsertab.UnsupportedOperationError

    def save_page(self):
        """Save the current page."""
        raise browsertab.UnsupportedOperationError

    def show_source(self):

        def show_source_cb(source):
            """Show source as soon as it's ready."""
            # WORKAROUND for https://github.com/PyCQA/pylint/issues/491
            # pylint: disable=no-member
            lexer = pygments.lexers.HtmlLexer()
            formatter = pygments.formatters.HtmlFormatter(
                full=True, linenos='table')
            # pylint: enable=no-member
            highlighted = pygments.highlight(source, lexer, formatter)

            tb = objreg.get('tabbed-browser', scope='window',
                            window=self._tab.win_id)
            new_tab = tb.tabopen(background=False, related=True)
            # The original URL becomes the path of a view-source: URL
            # (without a host), but query/fragment should stay.
            url = QUrl('view-source:' + urlstr)
            new_tab.set_html(highlighted, url)

        urlstr = self._tab.url().toString(QUrl.RemoveUserInfo)
        self._tab.dump_async(show_source_cb)


class WebKitPrinting(browsertab.AbstractPrinting):

    """QtWebKit implementations related to printing."""

    def check_pdf_support(self):
        pass

    def check_printer_support(self):
        pass

    def check_preview_support(self):
        pass

    def to_pdf(self, filename):
        printer = QPrinter()
        printer.setOutputFileName(filename)
        self.to_printer(printer)

    def to_printer(self, printer, callback=None):
        self._widget.print(printer)
        # Can't find out whether there was an error...
        if callback is not None:
            callback(True)


class WebKitSearch(browsertab.AbstractSearch):

    """QtWebKit implementations related to searching on the page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flags = QWebPage.FindFlags(0)

    def _call_cb(self, callback, found, text, flags, caller):
        """Call the given callback if it's non-None.

        Delays the call via a QTimer so the website is re-rendered in between.

        Args:
            callback: What to call
            found: If the text was found
            text: The text searched for
            flags: The flags searched with
            caller: Name of the caller.
        """
        found_text = 'found' if found else "didn't find"
        # Removing FindWrapsAroundDocument to get the same logging as with
        # QtWebEngine
        debug_flags = debug.qflags_key(
            QWebPage, flags & ~QWebPage.FindWrapsAroundDocument,
            klass=QWebPage.FindFlag)
        if debug_flags != '0x0000':
            flag_text = 'with flags {}'.format(debug_flags)
        else:
            flag_text = ''
        log.webview.debug(' '.join([caller, found_text, text, flag_text])
                          .strip())
        if callback is not None:
            QTimer.singleShot(0, functools.partial(callback, found))

    def clear(self):
        self.search_displayed = False
        # We first clear the marked text, then the highlights
        self._widget.findText('')
        self._widget.findText('', QWebPage.HighlightAllOccurrences)

    def search(self, text, *, ignore_case='never', reverse=False,
               result_cb=None):
        # Don't go to next entry on duplicate search
        if self.text == text and self.search_displayed:
            log.webview.debug("Ignoring duplicate search request"
                              " for {}".format(text))
            return

        # Clear old search results, this is done automatically on QtWebEngine.
        self.clear()

        self.text = text
        self.search_displayed = True
        self._flags = QWebPage.FindWrapsAroundDocument
        if self._is_case_sensitive(ignore_case):
            self._flags |= QWebPage.FindCaseSensitively
        if reverse:
            self._flags |= QWebPage.FindBackward
        # We actually search *twice* - once to highlight everything, then again
        # to get a mark so we can navigate.
        found = self._widget.findText(text, self._flags)
        self._widget.findText(text,
                              self._flags | QWebPage.HighlightAllOccurrences)
        self._call_cb(result_cb, found, text, self._flags, 'search')

    def next_result(self, *, result_cb=None):
        self.search_displayed = True
        found = self._widget.findText(self.text, self._flags)
        self._call_cb(result_cb, found, self.text, self._flags, 'next_result')

    def prev_result(self, *, result_cb=None):
        self.search_displayed = True
        # The int() here makes sure we get a copy of the flags.
        flags = QWebPage.FindFlags(int(self._flags))
        if flags & QWebPage.FindBackward:
            flags &= ~QWebPage.FindBackward
        else:
            flags |= QWebPage.FindBackward
        found = self._widget.findText(self.text, flags)
        self._call_cb(result_cb, found, self.text, flags, 'prev_result')


class WebKitCaret(browsertab.AbstractCaret):

    """QtWebKit implementations related to moving the cursor/selection."""

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_entered(self, mode):
        if mode != usertypes.KeyMode.caret:
            return

        self.selection_enabled = self._widget.hasSelection()
        self.selection_toggled.emit(self.selection_enabled)
        settings = self._widget.settings()
        settings.setAttribute(QWebSettings.CaretBrowsingEnabled, True)

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
            if not self.selection_enabled:
                self._widget.page().currentFrame().evaluateJavaScript(
                    utils.read_file('javascript/position_caret.js'))

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_left(self, _mode):
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
            if utils.is_windows:  # pragma: no cover
                act.append(QWebPage.MoveToPreviousChar)
        else:
            act = [QWebPage.SelectNextWord]
            if utils.is_windows:  # pragma: no cover
                act.append(QWebPage.SelectPreviousChar)
        for _ in range(count):
            for a in act:
                self._widget.triggerPageAction(a)

    def move_to_next_word(self, count=1):
        if not self.selection_enabled:
            act = [QWebPage.MoveToNextWord]
            if not utils.is_windows:  # pragma: no branch
                act.append(QWebPage.MoveToNextChar)
        else:
            act = [QWebPage.SelectNextWord]
            if not utils.is_windows:  # pragma: no branch
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
        self.selection_toggled.emit(self.selection_enabled)

    def drop_selection(self):
        self._widget.triggerPageAction(QWebPage.MoveToNextChar)

    def selection(self, callback):
        callback(self._widget.selectedText())

    def follow_selected(self, *, tab=False):
        if QWebSettings.globalSettings().testAttribute(
                QWebSettings.JavascriptEnabled):
            if tab:
                self._tab.data.override_target = usertypes.ClickTarget.tab
            self._tab.run_js_async(
                'window.getSelection().anchorNode.parentNode.click()')
        else:
            selection = self._widget.selectedHtml()
            if not selection:
                return
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


class WebKitScroller(browsertab.AbstractScroller):

    """QtWebKit implementations related to scrolling."""

    # FIXME:qtwebengine When to use the main frame, when the current one?

    def pos_px(self):
        return self._widget.page().mainFrame().scrollPosition()

    def pos_perc(self):
        return self._widget.scroll_pos

    def to_point(self, point):
        self._widget.page().mainFrame().setScrollPosition(point)

    def to_anchor(self, name):
        self._widget.page().mainFrame().scrollToAnchor(name)

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
                    frame = self._widget.page().mainFrame()
                    maximum = frame.scrollBarMaximum(orientation)
                    if maximum == 0:
                        continue
                    pos = int(maximum * val / 100)
                    pos = qtutils.check_overflow(pos, 'int', fatal=False)
                    frame.setScrollBarValue(orientation, pos)

    def _key_press(self, key, count=1, getter_name=None, direction=None):
        frame = self._widget.page().mainFrame()
        getter = None if getter_name is None else getattr(frame, getter_name)

        # FIXME:qtwebengine needed?
        # self._widget.setFocus()

        for _ in range(min(count, 5000)):
            # Abort scrolling if the minimum/maximum was reached.
            if (getter is not None and
                    frame.scrollBarValue(direction) == getter(direction)):
                return
            self._tab.key_press(key)

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

    def can_go_back(self):
        return self._history.canGoBack()

    def can_go_forward(self):
        return self._history.canGoForward()

    def _item_at(self, i):
        return self._history.itemAt(i)

    def _go_to_item(self, item):
        self._tab.predicted_navigation.emit(item.url())
        self._history.goToItem(item)

    def serialize(self):
        return qtutils.serialize(self._history)

    def deserialize(self, data):
        return qtutils.deserialize(data, self._history)

    def load_items(self, items):
        if items:
            self._tab.predicted_navigation.emit(items[-1].url)

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


class WebKitElements(browsertab.AbstractElements):

    """QtWebKit implemementations related to elements on the page."""

    def find_css(self, selector, callback, *, only_visible=False):
        mainframe = self._widget.page().mainFrame()
        if mainframe is None:
            raise browsertab.WebTabError("No frame focused!")

        elems = []
        frames = webkitelem.get_child_frames(mainframe)
        for f in frames:
            for elem in f.findAllElements(selector):
                elems.append(webkitelem.WebKitElement(elem, tab=self._tab))

        if only_visible:
            # pylint: disable=protected-access
            elems = [e for e in elems if e._is_visible(mainframe)]
            # pylint: enable=protected-access

        callback(elems)

    def find_id(self, elem_id, callback):
        def find_id_cb(elems):
            """Call the real callback with the found elements."""
            if not elems:
                callback(None)
            else:
                callback(elems[0])

        # Escape non-alphanumeric characters in the selector
        # https://www.w3.org/TR/CSS2/syndata.html#value-def-identifier
        elem_id = re.sub(r'[^a-zA-Z0-9_-]', r'\\\g<0>', elem_id)
        self.find_css('#' + elem_id, find_id_cb)

    def find_focused(self, callback):
        frame = self._widget.page().currentFrame()
        if frame is None:
            callback(None)
            return

        elem = frame.findFirstElement('*:focus')
        if elem.isNull():
            callback(None)
        else:
            callback(webkitelem.WebKitElement(elem, tab=self._tab))

    def find_at_pos(self, pos, callback):
        assert pos.x() >= 0
        assert pos.y() >= 0
        frame = self._widget.page().frameAt(pos)
        if frame is None:
            # This happens when we click inside the webview, but not actually
            # on the QWebPage - for example when clicking the scrollbar
            # sometimes.
            log.webview.debug("Hit test at {} but frame is None!".format(pos))
            callback(None)
            return

        # You'd think we have to subtract frame.geometry().topLeft() from the
        # position, but it seems QWebFrame::hitTestContent wants a position
        # relative to the QWebView, not to the frame. This makes no sense to
        # me, but it works this way.
        hitresult = frame.hitTestContent(pos)
        if hitresult.isNull():
            # For some reason, the whole hit result can be null sometimes (e.g.
            # on doodle menu links).
            log.webview.debug("Hit test result is null!")
            callback(None)
            return

        try:
            elem = webkitelem.WebKitElement(hitresult.element(), tab=self._tab)
        except webkitelem.IsNullError:
            # For some reason, the hit result element can be a null element
            # sometimes (e.g. when clicking the timetable fields on
            # http://www.sbb.ch/ ).
            log.webview.debug("Hit test result element is null!")
            callback(None)
            return

        callback(elem)


class WebKitTab(browsertab.AbstractTab):

    """A QtWebKit tab in the browser."""

    def __init__(self, *, win_id, mode_manager, private, parent=None):
        super().__init__(win_id=win_id, mode_manager=mode_manager,
                         private=private, parent=parent)
        widget = webview.WebView(win_id=win_id, tab_id=self.tab_id,
                                 private=private, tab=self)
        if private:
            self._make_private(widget)
        self.history = WebKitHistory(self)
        self.scroller = WebKitScroller(self, parent=self)
        self.caret = WebKitCaret(mode_manager=mode_manager,
                                 tab=self, parent=self)
        self.zoom = WebKitZoom(tab=self, parent=self)
        self.search = WebKitSearch(parent=self)
        self.printing = WebKitPrinting()
        self.elements = WebKitElements(tab=self)
        self.action = WebKitAction(tab=self)
        # We're assigning settings in _set_widget
        self.settings = webkitsettings.WebKitSettings(settings=None)
        self._set_widget(widget)
        self._connect_signals()
        self.backend = usertypes.Backend.QtWebKit

    def _install_event_filter(self):
        self._widget.installEventFilter(self._mouse_event_filter)

    def _make_private(self, widget):
        settings = widget.settings()
        settings.setAttribute(QWebSettings.PrivateBrowsingEnabled, True)

    def openurl(self, url, *, predict=True):
        self._openurl_prepare(url, predict=predict)
        self._widget.openurl(url)

    def url(self, requested=False):
        frame = self._widget.page().mainFrame()
        if requested:
            return frame.requestedUrl()
        else:
            return frame.url()

    def dump_async(self, callback, *, plain=False):
        frame = self._widget.page().mainFrame()
        if plain:
            callback(frame.toPlainText())
        else:
            callback(frame.toHtml())

    def run_js_async(self, code, callback=None, *, world=None):
        if world is not None and world != usertypes.JsWorld.jseval:
            log.webview.warning("Ignoring world ID {}".format(world))
        document_element = self._widget.page().mainFrame().documentElement()
        result = document_element.evaluateJavaScript(code)
        if callback is not None:
            callback(result)

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
        self.networkaccessmanager().clear_all_ssl_errors()

    def key_press(self, key, modifier=Qt.NoModifier):
        press_evt = QKeyEvent(QEvent.KeyPress, key, modifier, 0, 0, 0)
        release_evt = QKeyEvent(QEvent.KeyRelease, key, modifier,
                                0, 0, 0)
        self.send_event(press_evt)
        self.send_event(release_evt)

    @pyqtSlot()
    def _on_history_trigger(self):
        url = self.url()
        requested_url = self.url(requested=True)
        self.add_history_item.emit(url, requested_url, self.title())

    def set_html(self, html, base_url=QUrl()):
        self._widget.setHtml(html, base_url)

    def networkaccessmanager(self):
        return self._widget.page().networkAccessManager()

    def user_agent(self):
        page = self._widget.page()
        return page.userAgentForUrl(self.url())

    @pyqtSlot()
    def _on_load_started(self):
        super()._on_load_started()
        self.networkaccessmanager().netrc_used = False
        # Make sure the icon is cleared when navigating to a page without one.
        self.icon_changed.emit(QIcon())

    @pyqtSlot()
    def _on_frame_load_finished(self):
        """Make sure we emit an appropriate status when loading finished.

        While Qt has a bool "ok" attribute for loadFinished, it always is True
        when using error pages... See
        https://github.com/qutebrowser/qutebrowser/issues/84
        """
        self._on_load_finished(not self._widget.page().error_occurred)

    @pyqtSlot()
    def _on_webkit_icon_changed(self):
        """Emit iconChanged with a QIcon like QWebEngineView does."""
        if sip.isdeleted(self._widget):
            log.webview.debug("Got _on_webkit_icon_changed for deleted view!")
            return
        self.icon_changed.emit(self._widget.icon())

    @pyqtSlot(QWebFrame)
    def _on_frame_created(self, frame):
        """Connect the contentsSizeChanged signal of each frame."""
        # FIXME:qtwebengine those could theoretically regress:
        # https://github.com/qutebrowser/qutebrowser/issues/152
        # https://github.com/qutebrowser/qutebrowser/issues/263
        frame.contentsSizeChanged.connect(self._on_contents_size_changed)

    @pyqtSlot(QSize)
    def _on_contents_size_changed(self, size):
        self.contents_size_changed.emit(QSizeF(size))

    @pyqtSlot(usertypes.NavigationRequest)
    def _on_navigation_request(self, navigation):
        super()._on_navigation_request(navigation)
        if not navigation.accepted:
            return

        log.webview.debug("target {} override {}".format(
            self.data.open_target, self.data.override_target))

        if self.data.override_target is not None:
            target = self.data.override_target
            self.data.override_target = None
        else:
            target = self.data.open_target

        if (navigation.navigation_type == navigation.Type.link_clicked and
                target != usertypes.ClickTarget.normal):
            tab = shared.get_tab(self.win_id, target)
            tab.openurl(navigation.url)
            self.data.open_target = usertypes.ClickTarget.normal
            navigation.accepted = False

        if navigation.is_main_frame:
            self.settings.update_for_url(navigation.url)

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
        page.frameCreated.connect(self._on_frame_created)
        frame.contentsSizeChanged.connect(self._on_contents_size_changed)
        frame.initialLayoutCompleted.connect(self._on_history_trigger)
        page.navigation_request.connect(self._on_navigation_request)

    def event_target(self):
        return self._widget
