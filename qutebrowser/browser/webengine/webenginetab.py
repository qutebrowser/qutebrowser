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

"""Wrapper over a QWebEngineView."""

import math
import functools
import sys
import re
import html as html_utils

import sip
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, Qt, QEvent, QPoint, QPointF,
                          QUrl, QTimer)
from PyQt5.QtGui import QKeyEvent, QIcon
from PyQt5.QtNetwork import QAuthenticator
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineScript

from qutebrowser.config import configdata, config
from qutebrowser.browser import browsertab, mouse, shared
from qutebrowser.browser.webengine import (webview, webengineelem, tabhistory,
                                           interceptor, webenginequtescheme,
                                           webenginedownloads,
                                           webenginesettings)
from qutebrowser.misc import miscwidgets
from qutebrowser.utils import (usertypes, qtutils, log, javascript, utils,
                               message, objreg, jinja, debug)


_qute_scheme_handler = None


def init():
    """Initialize QtWebEngine-specific modules."""
    # For some reason we need to keep a reference, otherwise the scheme handler
    # won't work...
    # https://www.riverbankcomputing.com/pipermail/pyqt/2016-September/038075.html
    global _qute_scheme_handler

    app = QApplication.instance()
    log.init.debug("Initializing qute://* handler...")
    _qute_scheme_handler = webenginequtescheme.QuteSchemeHandler(parent=app)
    _qute_scheme_handler.install(webenginesettings.default_profile)
    _qute_scheme_handler.install(webenginesettings.private_profile)

    log.init.debug("Initializing request interceptor...")
    host_blocker = objreg.get('host-blocker')
    req_interceptor = interceptor.RequestInterceptor(
        host_blocker, parent=app)
    req_interceptor.install(webenginesettings.default_profile)
    req_interceptor.install(webenginesettings.private_profile)

    log.init.debug("Initializing QtWebEngine downloads...")
    download_manager = webenginedownloads.DownloadManager(parent=app)
    download_manager.install(webenginesettings.default_profile)
    download_manager.install(webenginesettings.private_profile)
    objreg.register('webengine-download-manager', download_manager)


# Mapping worlds from usertypes.JsWorld to QWebEngineScript world IDs.
_JS_WORLD_MAP = {
    usertypes.JsWorld.main: QWebEngineScript.MainWorld,
    usertypes.JsWorld.application: QWebEngineScript.ApplicationWorld,
    usertypes.JsWorld.user: QWebEngineScript.UserWorld,
    usertypes.JsWorld.jseval: QWebEngineScript.UserWorld + 1,
}


class WebEngineAction(browsertab.AbstractAction):

    """QtWebEngine implementations related to web actions."""

    action_class = QWebEnginePage
    action_base = QWebEnginePage.WebAction

    def exit_fullscreen(self):
        self._widget.triggerPageAction(QWebEnginePage.ExitFullScreen)

    def save_page(self):
        """Save the current page."""
        self._widget.triggerPageAction(QWebEnginePage.SavePage)

    def show_source(self):
        try:
            self._widget.triggerPageAction(QWebEnginePage.ViewSource)
        except AttributeError:
            # Qt < 5.8
            tb = objreg.get('tabbed-browser', scope='window',
                            window=self._tab.win_id)
            urlstr = self._tab.url().toString(QUrl.RemoveUserInfo)
            # The original URL becomes the path of a view-source: URL
            # (without a host), but query/fragment should stay.
            url = QUrl('view-source:' + urlstr)
            tb.tabopen(url, background=False, related=True)


class WebEnginePrinting(browsertab.AbstractPrinting):

    """QtWebEngine implementations related to printing."""

    def check_pdf_support(self):
        return True

    def check_printer_support(self):
        if not hasattr(self._widget.page(), 'print'):
            raise browsertab.WebTabError(
                "Printing is unsupported with QtWebEngine on Qt < 5.8")

    def check_preview_support(self):
        raise browsertab.WebTabError(
            "Print previews are unsupported with QtWebEngine")

    def to_pdf(self, filename):
        self._widget.page().printToPdf(filename)

    def to_printer(self, printer, callback=None):
        if callback is None:
            callback = lambda _ok: None
        self._widget.page().print(printer, callback)


class WebEngineSearch(browsertab.AbstractSearch):

    """QtWebEngine implementations related to searching on the page.

    Attributes:
        _flags: The QWebEnginePage.FindFlags of the last search.
        _pending_searches: How many searches have been started but not called
                           back yet.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flags = QWebEnginePage.FindFlags(0)
        self._pending_searches = 0

    def _find(self, text, flags, callback, caller):
        """Call findText on the widget."""
        self.search_displayed = True
        self._pending_searches += 1

        def wrapped_callback(found):
            """Wrap the callback to do debug logging."""
            self._pending_searches -= 1
            if self._pending_searches > 0:
                # See https://github.com/qutebrowser/qutebrowser/issues/2442
                # and https://github.com/qt/qtwebengine/blob/5.10/src/core/web_contents_adapter.cpp#L924-L934
                log.webview.debug("Ignoring cancelled search callback with "
                                  "{} pending searches".format(
                                      self._pending_searches))
                return

            found_text = 'found' if found else "didn't find"
            if flags:
                flag_text = 'with flags {}'.format(debug.qflags_key(
                    QWebEnginePage, flags, klass=QWebEnginePage.FindFlag))
            else:
                flag_text = ''
            log.webview.debug(' '.join([caller, found_text, text, flag_text])
                              .strip())
            if callback is not None:
                callback(found)
        self._widget.findText(text, flags, wrapped_callback)

    def search(self, text, *, ignore_case='never', reverse=False,
               result_cb=None):
        # Don't go to next entry on duplicate search
        if self.text == text and self.search_displayed:
            log.webview.debug("Ignoring duplicate search request"
                              " for {}".format(text))
            return

        self.text = text
        self._flags = QWebEnginePage.FindFlags(0)
        if self._is_case_sensitive(ignore_case):
            self._flags |= QWebEnginePage.FindCaseSensitively
        if reverse:
            self._flags |= QWebEnginePage.FindBackward

        self._find(text, self._flags, result_cb, 'search')

    def clear(self):
        self.search_displayed = False
        self._widget.findText('')

    def prev_result(self, *, result_cb=None):
        # The int() here makes sure we get a copy of the flags.
        flags = QWebEnginePage.FindFlags(int(self._flags))
        if flags & QWebEnginePage.FindBackward:
            flags &= ~QWebEnginePage.FindBackward
        else:
            flags |= QWebEnginePage.FindBackward
        self._find(self.text, flags, result_cb, 'prev_result')

    def next_result(self, *, result_cb=None):
        self._find(self.text, self._flags, result_cb, 'next_result')


class WebEngineCaret(browsertab.AbstractCaret):

    """QtWebEngine implementations related to moving the cursor/selection."""

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_entered(self, mode):
        if mode != usertypes.KeyMode.caret:
            return

        if self._tab.search.search_displayed:
            # We are currently in search mode.
            # convert the search to a blue selection so we can operate on it
            # https://bugreports.qt.io/browse/QTBUG-60673
            self._tab.search.clear()

        self._tab.run_js_async(
            javascript.assemble('caret', 'setPlatform', sys.platform))
        self._js_call('setInitialCursor', self._selection_cb)

    def _selection_cb(self, enabled):
        """Emit selection_toggled based on setInitialCursor."""
        if enabled is None:
            log.webview.debug("Ignoring selection status None")
            return
        self.selection_toggled.emit(enabled)

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_left(self, mode):
        if mode != usertypes.KeyMode.caret:
            return

        self.drop_selection()
        self._js_call('disableCaret')

    def move_to_next_line(self, count=1):
        for _ in range(count):
            self._js_call('moveDown')

    def move_to_prev_line(self, count=1):
        for _ in range(count):
            self._js_call('moveUp')

    def move_to_next_char(self, count=1):
        for _ in range(count):
            self._js_call('moveRight')

    def move_to_prev_char(self, count=1):
        for _ in range(count):
            self._js_call('moveLeft')

    def move_to_end_of_word(self, count=1):
        for _ in range(count):
            self._js_call('moveToEndOfWord')

    def move_to_next_word(self, count=1):
        for _ in range(count):
            self._js_call('moveToNextWord')

    def move_to_prev_word(self, count=1):
        for _ in range(count):
            self._js_call('moveToPreviousWord')

    def move_to_start_of_line(self):
        self._js_call('moveToStartOfLine')

    def move_to_end_of_line(self):
        self._js_call('moveToEndOfLine')

    def move_to_start_of_next_block(self, count=1):
        for _ in range(count):
            self._js_call('moveToStartOfNextBlock')

    def move_to_start_of_prev_block(self, count=1):
        for _ in range(count):
            self._js_call('moveToStartOfPrevBlock')

    def move_to_end_of_next_block(self, count=1):
        for _ in range(count):
            self._js_call('moveToEndOfNextBlock')

    def move_to_end_of_prev_block(self, count=1):
        for _ in range(count):
            self._js_call('moveToEndOfPrevBlock')

    def move_to_start_of_document(self):
        self._js_call('moveToStartOfDocument')

    def move_to_end_of_document(self):
        self._js_call('moveToEndOfDocument')

    def toggle_selection(self):
        self._js_call('toggleSelection', self.selection_toggled.emit)

    def drop_selection(self):
        self._js_call('dropSelection')

    def selection(self, callback):
        # Not using selectedText() as WORKAROUND for
        # https://bugreports.qt.io/browse/QTBUG-53134
        # Even on Qt 5.10 selectedText() seems to work poorly, see
        # https://github.com/qutebrowser/qutebrowser/issues/3523
        self._tab.run_js_async(javascript.assemble('caret', 'getSelection'),
                               callback)

    def _follow_selected_cb(self, js_elem, tab=False):
        """Callback for javascript which clicks the selected element.

        Args:
            js_elem: The element serialized from javascript.
            tab: Open in a new tab.
        """
        if js_elem is None:
            return
        assert isinstance(js_elem, dict), js_elem
        elem = webengineelem.WebEngineElement(js_elem, tab=self._tab)
        if tab:
            click_type = usertypes.ClickTarget.tab
        else:
            click_type = usertypes.ClickTarget.normal

        # Only click if we see a link
        if elem.is_link():
            log.webview.debug("Found link in selection, clicking. ClickTarget "
                              "{}, elem {}".format(click_type, elem))
            elem.click(click_type)

    def follow_selected(self, *, tab=False):
        if self._tab.search.search_displayed:
            # We are currently in search mode.
            # let's click the link via a fake-click
            # https://bugreports.qt.io/browse/QTBUG-60673
            self._tab.search.clear()

            log.webview.debug("Clicking a searched link via fake key press.")
            # send a fake enter, clicking the orange selection box
            if tab:
                self._tab.key_press(Qt.Key_Enter, modifier=Qt.ControlModifier)
            else:
                self._tab.key_press(Qt.Key_Enter)

        else:
            # click an existing blue selection
            js_code = javascript.assemble('webelem', 'find_selected_link')
            self._tab.run_js_async(js_code, lambda jsret:
                                   self._follow_selected_cb(jsret, tab))

    def _js_call(self, command, callback=None):
        self._tab.run_js_async(javascript.assemble('caret', command), callback)


class WebEngineScroller(browsertab.AbstractScroller):

    """QtWebEngine implementations related to scrolling."""

    def __init__(self, tab, parent=None):
        super().__init__(tab, parent)
        self._args = objreg.get('args')
        self._pos_perc = (0, 0)
        self._pos_px = QPoint()
        self._at_bottom = False

    def _init_widget(self, widget):
        super()._init_widget(widget)
        page = widget.page()
        page.scrollPositionChanged.connect(self._update_pos)

    def _repeated_key_press(self, key, count=1, modifier=Qt.NoModifier):
        """Send count fake key presses to this scroller's WebEngineTab."""
        for _ in range(min(count, 1000)):
            self._tab.key_press(key, modifier)

    @pyqtSlot(QPointF)
    def _update_pos(self, pos):
        """Update the scroll position attributes when it changed."""
        self._pos_px = pos.toPoint()
        contents_size = self._widget.page().contentsSize()

        scrollable_x = contents_size.width() - self._widget.width()
        if scrollable_x == 0:
            perc_x = 0
        else:
            try:
                perc_x = min(100, round(100 / scrollable_x * pos.x()))
            except ValueError:
                # https://github.com/qutebrowser/qutebrowser/issues/3219
                log.misc.debug("Got ValueError!")
                log.misc.debug("contents_size.width(): {}".format(
                    contents_size.width()))
                log.misc.debug("self._widget.width(): {}".format(
                    self._widget.width()))
                log.misc.debug("scrollable_x: {}".format(scrollable_x))
                log.misc.debug("pos.x(): {}".format(pos.x()))
                raise

        scrollable_y = contents_size.height() - self._widget.height()
        if scrollable_y == 0:
            perc_y = 0
        else:
            perc_y = min(100, round(100 / scrollable_y * pos.y()))

        self._at_bottom = math.ceil(pos.y()) >= scrollable_y

        if (self._pos_perc != (perc_x, perc_y) or
                'no-scroll-filtering' in self._args.debug_flags):
            self._pos_perc = perc_x, perc_y
            self.perc_changed.emit(*self._pos_perc)

    def pos_px(self):
        return self._pos_px

    def pos_perc(self):
        return self._pos_perc

    def to_perc(self, x=None, y=None):
        js_code = javascript.assemble('scroll', 'to_perc', x, y)
        self._tab.run_js_async(js_code)

    def to_point(self, point):
        js_code = javascript.assemble('window', 'scroll', point.x(), point.y())
        self._tab.run_js_async(js_code)

    def to_anchor(self, name):
        url = self._tab.url()
        url.setFragment(name)
        self._tab.openurl(url)

    def delta(self, x=0, y=0):
        self._tab.run_js_async(javascript.assemble('window', 'scrollBy', x, y))

    def delta_page(self, x=0, y=0):
        js_code = javascript.assemble('scroll', 'delta_page', x, y)
        self._tab.run_js_async(js_code)

    def up(self, count=1):
        self._repeated_key_press(Qt.Key_Up, count)

    def down(self, count=1):
        self._repeated_key_press(Qt.Key_Down, count)

    def left(self, count=1):
        self._repeated_key_press(Qt.Key_Left, count)

    def right(self, count=1):
        self._repeated_key_press(Qt.Key_Right, count)

    def top(self):
        self._tab.key_press(Qt.Key_Home)

    def bottom(self):
        self._tab.key_press(Qt.Key_End)

    def page_up(self, count=1):
        self._repeated_key_press(Qt.Key_PageUp, count)

    def page_down(self, count=1):
        self._repeated_key_press(Qt.Key_PageDown, count)

    def at_top(self):
        return self.pos_px().y() == 0

    def at_bottom(self):
        return self._at_bottom


class WebEngineHistory(browsertab.AbstractHistory):

    """QtWebEngine implementations related to page history."""

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
        if not qtutils.version_check('5.9', compiled=False):
            # WORKAROUND for
            # https://github.com/qutebrowser/qutebrowser/issues/2289
            # Don't use the history's currentItem here, because of
            # https://bugreports.qt.io/browse/QTBUG-59599 and because it doesn't
            # contain view-source.
            scheme = self._tab.url().scheme()
            if scheme in ['view-source', 'chrome']:
                raise browsertab.WebTabError("Can't serialize special URL!")
        return qtutils.serialize(self._history)

    def deserialize(self, data):
        return qtutils.deserialize(data, self._history)

    def load_items(self, items):
        if items:
            self._tab.predicted_navigation.emit(items[-1].url)

        stream, _data, cur_data = tabhistory.serialize(items)
        qtutils.deserialize_stream(stream, self._history)

        @pyqtSlot()
        def _on_load_finished():
            self._tab.scroller.to_point(cur_data['scroll-pos'])
            self._tab.load_finished.disconnect(_on_load_finished)

        if cur_data is not None:
            if 'zoom' in cur_data:
                self._tab.zoom.set_factor(cur_data['zoom'])
            if ('scroll-pos' in cur_data and
                    self._tab.scroller.pos_px() == QPoint(0, 0)):
                self._tab.load_finished.connect(_on_load_finished)


class WebEngineZoom(browsertab.AbstractZoom):

    """QtWebEngine implementations related to zooming."""

    def _set_factor_internal(self, factor):
        self._widget.setZoomFactor(factor)


class WebEngineElements(browsertab.AbstractElements):

    """QtWebEngine implemementations related to elements on the page."""

    def _js_cb_multiple(self, callback, js_elems):
        """Handle found elements coming from JS and call the real callback.

        Args:
            callback: The callback to call with the found elements.
                      Called with None if there was an error.
            js_elems: The elements serialized from javascript.
        """
        if js_elems is None:
            callback(None)
            return

        elems = []
        for js_elem in js_elems:
            elem = webengineelem.WebEngineElement(js_elem, tab=self._tab)
            elems.append(elem)
        callback(elems)

    def _js_cb_single(self, callback, js_elem):
        """Handle a found focus elem coming from JS and call the real callback.

        Args:
            callback: The callback to call with the found element.
                      Called with a WebEngineElement or None.
            js_elem: The element serialized from javascript.
        """
        debug_str = ('None' if js_elem is None
                     else utils.elide(repr(js_elem), 1000))
        log.webview.debug("Got element from JS: {}".format(debug_str))

        if js_elem is None:
            callback(None)
        else:
            elem = webengineelem.WebEngineElement(js_elem, tab=self._tab)
            callback(elem)

    def find_css(self, selector, callback, *, only_visible=False):
        js_code = javascript.assemble('webelem', 'find_css', selector,
                                      only_visible)
        js_cb = functools.partial(self._js_cb_multiple, callback)
        self._tab.run_js_async(js_code, js_cb)

    def find_id(self, elem_id, callback):
        js_code = javascript.assemble('webelem', 'find_id', elem_id)
        js_cb = functools.partial(self._js_cb_single, callback)
        self._tab.run_js_async(js_code, js_cb)

    def find_focused(self, callback):
        js_code = javascript.assemble('webelem', 'find_focused')
        js_cb = functools.partial(self._js_cb_single, callback)
        self._tab.run_js_async(js_code, js_cb)

    def find_at_pos(self, pos, callback):
        assert pos.x() >= 0
        assert pos.y() >= 0
        pos /= self._tab.zoom.factor()
        js_code = javascript.assemble('webelem', 'find_at_pos',
                                      pos.x(), pos.y())
        js_cb = functools.partial(self._js_cb_single, callback)
        self._tab.run_js_async(js_code, js_cb)


class WebEngineTab(browsertab.AbstractTab):

    """A QtWebEngine tab in the browser.

    Signals:
        _load_finished_fake:
            Used in place of unreliable loadFinished
    """

    # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-65223
    _load_finished_fake = pyqtSignal(bool)

    def __init__(self, *, win_id, mode_manager, private, parent=None):
        super().__init__(win_id=win_id, mode_manager=mode_manager,
                         private=private, parent=parent)
        widget = webview.WebEngineView(tabdata=self.data, win_id=win_id,
                                       private=private)
        self.history = WebEngineHistory(self)
        self.scroller = WebEngineScroller(self, parent=self)
        self.caret = WebEngineCaret(mode_manager=mode_manager,
                                    tab=self, parent=self)
        self.zoom = WebEngineZoom(tab=self, parent=self)
        self.search = WebEngineSearch(parent=self)
        self.printing = WebEnginePrinting()
        self.elements = WebEngineElements(tab=self)
        self.action = WebEngineAction(tab=self)
        # We're assigning settings in _set_widget
        self.settings = webenginesettings.WebEngineSettings(settings=None)
        self._set_widget(widget)
        self._connect_signals()
        self.backend = usertypes.Backend.QtWebEngine
        self._child_event_filter = None
        self._saved_zoom = None
        self._reload_url = None
        config.instance.changed.connect(self._on_config_changed)
        self._init_js()

    @pyqtSlot(str)
    def _on_config_changed(self, option):
        if option in ['scrolling.bar', 'content.user_stylesheets']:
            self._init_stylesheet()
            self._update_stylesheet()

    def _update_stylesheet(self):
        """Update the custom stylesheet in existing tabs."""
        css = shared.get_user_stylesheet()
        code = javascript.assemble('stylesheet', 'set_css', css)
        self.run_js_async(code)

    def _inject_early_js(self, name, js_code, *,
                         world=QWebEngineScript.ApplicationWorld,
                         subframes=False):
        """Inject the given script to run early on a page load.

        This runs the script both on DocumentCreation and DocumentReady as on
        some internal pages, DocumentCreation will not work.

        That is a WORKAROUND for https://bugreports.qt.io/browse/QTBUG-66011
        """
        scripts = self._widget.page().scripts()
        for injection in ['creation', 'ready']:
            injection_points = {
                'creation': QWebEngineScript.DocumentCreation,
                'ready': QWebEngineScript.DocumentReady,
            }
            script = QWebEngineScript()
            script.setInjectionPoint(injection_points[injection])
            script.setSourceCode(js_code)
            script.setWorldId(world)
            script.setRunsOnSubFrames(subframes)
            script.setName('_qute_{}_{}'.format(name, injection))
            scripts.insert(script)

    def _remove_early_js(self, name):
        """Remove an early QWebEngineScript."""
        scripts = self._widget.page().scripts()
        for injection in ['creation', 'ready']:
            full_name = '_qute_{}_{}'.format(name, injection)
            script = scripts.findScript(full_name)
            if not script.isNull():
                scripts.remove(script)

    def _init_js(self):
        """Initialize global qutebrowser JavaScript."""
        js_code = javascript.wrap_global(
            'scripts',
            utils.read_file('javascript/scroll.js'),
            utils.read_file('javascript/webelem.js'),
            utils.read_file('javascript/caret.js'),
        )
        # FIXME:qtwebengine what about subframes=True?
        self._inject_early_js('js', js_code, subframes=True)
        self._init_stylesheet()

        greasemonkey = objreg.get('greasemonkey')
        greasemonkey.scripts_reloaded.connect(self._inject_userscripts)
        self._inject_userscripts()

    def _init_stylesheet(self):
        """Initialize custom stylesheets.

        Partially inspired by QupZilla:
        https://github.com/QupZilla/qupzilla/blob/v2.0/src/lib/app/mainapplication.cpp#L1063-L1101
        """
        self._remove_early_js('stylesheet')
        css = shared.get_user_stylesheet()
        js_code = javascript.wrap_global(
            'stylesheet',
            utils.read_file('javascript/stylesheet.js'),
            javascript.assemble('stylesheet', 'set_css', css),
        )
        self._inject_early_js('stylesheet', js_code, subframes=True)

    def _inject_userscripts(self):
        """Register user JavaScript files with the global profiles."""
        # The Greasemonkey metadata block support in QtWebEngine only starts at
        # Qt 5.8. With 5.7.1, we need to inject the scripts ourselves in
        # response to urlChanged.
        if not qtutils.version_check('5.8'):
            return

        # Since we are inserting scripts into profile.scripts they won't
        # just get replaced by new gm scripts like if we were injecting them
        # ourselves so we need to remove all gm scripts, while not removing
        # any other stuff that might have been added. Like the one for
        # stylesheets.
        greasemonkey = objreg.get('greasemonkey')
        scripts = self._widget.page().scripts()
        for script in scripts.toList():
            if script.name().startswith("GM-"):
                log.greasemonkey.debug('Removing script: {}'
                                       .format(script.name()))
                removed = scripts.remove(script)
                assert removed, script.name()

        # Then add the new scripts.
        for script in greasemonkey.all_scripts():
            # @run-at (and @include/@exclude/@match) is parsed by
            # QWebEngineScript.
            new_script = QWebEngineScript()
            new_script.setWorldId(QWebEngineScript.MainWorld)
            new_script.setSourceCode(script.code())
            new_script.setName("GM-{}".format(script.name))
            new_script.setRunsOnSubFrames(script.runs_on_sub_frames)
            log.greasemonkey.debug('adding script: {}'
                                   .format(new_script.name()))
            scripts.insert(new_script)

    def _install_event_filter(self):
        fp = self._widget.focusProxy()
        if fp is not None:
            fp.installEventFilter(self._mouse_event_filter)
        self._child_event_filter = mouse.ChildEventFilter(
            eventfilter=self._mouse_event_filter, widget=self._widget,
            parent=self)
        self._widget.installEventFilter(self._child_event_filter)

    @pyqtSlot()
    def _restore_zoom(self):
        if sip.isdeleted(self._widget):
            # https://github.com/qutebrowser/qutebrowser/issues/3498
            return
        if self._saved_zoom is None:
            return
        self.zoom.set_factor(self._saved_zoom)
        self._saved_zoom = None

    def openurl(self, url, *, predict=True):
        """Open the given URL in this tab.

        Arguments:
            url: The QUrl to open.
            predict: If set to False, predicted_navigation is not emitted.
        """
        self._saved_zoom = self.zoom.factor()
        self._openurl_prepare(url, predict=predict)
        self._widget.load(url)

    def url(self, requested=False):
        page = self._widget.page()
        if requested:
            return page.requestedUrl()
        else:
            return page.url()

    def dump_async(self, callback, *, plain=False):
        if plain:
            self._widget.page().toPlainText(callback)
        else:
            self._widget.page().toHtml(callback)

    def run_js_async(self, code, callback=None, *, world=None):
        if world is None:
            world_id = QWebEngineScript.ApplicationWorld
        elif isinstance(world, int):
            world_id = world
        else:
            world_id = _JS_WORLD_MAP[world]

        if callback is None:
            self._widget.page().runJavaScript(code, world_id)
        else:
            self._widget.page().runJavaScript(code, world_id, callback)

    def shutdown(self):
        self.shutting_down.emit()
        self.action.exit_fullscreen()
        self._widget.shutdown()

    def reload(self, *, force=False):
        if force:
            action = QWebEnginePage.ReloadAndBypassCache
        else:
            action = QWebEnginePage.Reload
        self._widget.triggerPageAction(action)

    def stop(self):
        self._widget.stop()

    def title(self):
        return self._widget.title()

    def icon(self):
        return self._widget.icon()

    def set_html(self, html, base_url=QUrl()):
        # FIXME:qtwebengine
        # check this and raise an exception if too big:
        # Warning: The content will be percent encoded before being sent to the
        # renderer via IPC. This may increase its size. The maximum size of the
        # percent encoded content is 2 megabytes minus 30 bytes.
        self._widget.setHtml(html, base_url)

    def networkaccessmanager(self):
        return None

    def user_agent(self):
        return None

    def clear_ssl_errors(self):
        raise browsertab.UnsupportedOperationError

    def key_press(self, key, modifier=Qt.NoModifier):
        press_evt = QKeyEvent(QEvent.KeyPress, key, modifier, 0, 0, 0)
        release_evt = QKeyEvent(QEvent.KeyRelease, key, modifier,
                                0, 0, 0)
        self.send_event(press_evt)
        self.send_event(release_evt)

    def _show_error_page(self, url, error):
        """Show an error page in the tab."""
        log.misc.debug("Showing error page for {}".format(error))
        url_string = url.toDisplayString()
        error_page = jinja.render(
            'error.html',
            title="Error loading page: {}".format(url_string),
            url=url_string, error=error)
        self.set_html(error_page)

    @pyqtSlot()
    def _on_history_trigger(self):
        try:
            self._widget.page()
        except RuntimeError:
            # Looks like this slot can be triggered on destroyed tabs:
            # https://crashes.qutebrowser.org/view/3abffbed (Qt 5.9.1)
            # wrapped C/C++ object of type WebEngineView has been deleted
            log.misc.debug("Ignoring history trigger for destroyed tab")
            return

        url = self.url()
        requested_url = self.url(requested=True)

        # Don't save the title if it's generated from the URL
        title = self.title()
        title_url = QUrl(url)
        title_url.setScheme('')
        if title == title_url.toDisplayString(QUrl.RemoveScheme).strip('/'):
            title = ""

        # Don't add history entry if the URL is invalid anyways
        if not url.isValid():
            log.misc.debug("Ignoring invalid URL being added to history")
            return

        self.add_history_item.emit(url, requested_url, title)

    @pyqtSlot(QUrl, 'QAuthenticator*', 'QString')
    def _on_proxy_authentication_required(self, url, authenticator,
                                          proxy_host):
        """Called when a proxy needs authentication."""
        msg = "<b>{}</b> requires a username and password.".format(
            html_utils.escape(proxy_host))
        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
        answer = message.ask(
            title="Proxy authentication required", text=msg,
            mode=usertypes.PromptMode.user_pwd,
            abort_on=[self.shutting_down, self.load_started], url=urlstr)
        if answer is not None:
            authenticator.setUser(answer.user)
            authenticator.setPassword(answer.password)
        else:
            try:
                # pylint: disable=no-member, useless-suppression
                sip.assign(authenticator, QAuthenticator())
                # pylint: enable=no-member, useless-suppression
            except AttributeError:
                self._show_error_page(url, "Proxy authentication required")

    @pyqtSlot(QUrl, 'QAuthenticator*')
    def _on_authentication_required(self, url, authenticator):
        netrc_success = False
        if not self.data.netrc_used:
            self.data.netrc_used = True
            netrc_success = shared.netrc_authentication(url, authenticator)
        if not netrc_success:
            abort_on = [self.shutting_down, self.load_started]
            answer = shared.authentication_required(url, authenticator,
                                                    abort_on)
        if not netrc_success and answer is None:
            try:
                # pylint: disable=no-member, useless-suppression
                sip.assign(authenticator, QAuthenticator())
                # pylint: enable=no-member, useless-suppression
            except AttributeError:
                # WORKAROUND for
                # https://www.riverbankcomputing.com/pipermail/pyqt/2016-December/038400.html
                self._show_error_page(url, "Authentication required")

    @pyqtSlot('QWebEngineFullScreenRequest')
    def _on_fullscreen_requested(self, request):
        request.accept()
        on = request.toggleOn()

        self.data.fullscreen = on
        self.fullscreen_requested.emit(on)
        if on:
            notification = miscwidgets.FullscreenNotification(self)
            notification.show()
            notification.set_timeout(3000)

    @pyqtSlot()
    def _on_load_started(self):
        """Clear search when a new load is started if needed."""
        if (qtutils.version_check('5.9', compiled=False) and
                not qtutils.version_check('5.9.2', compiled=False)):
            # WORKAROUND for
            # https://bugreports.qt.io/browse/QTBUG-61506
            self.search.clear()
        super()._on_load_started()
        self.data.netrc_used = False

    @pyqtSlot(QWebEnginePage.RenderProcessTerminationStatus, int)
    def _on_render_process_terminated(self, status, exitcode):
        """Show an error when the renderer process terminated."""
        if (status == QWebEnginePage.AbnormalTerminationStatus and
                exitcode == 256):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-58697
            status = QWebEnginePage.CrashedTerminationStatus

        status_map = {
            QWebEnginePage.NormalTerminationStatus:
                browsertab.TerminationStatus.normal,
            QWebEnginePage.AbnormalTerminationStatus:
                browsertab.TerminationStatus.abnormal,
            QWebEnginePage.CrashedTerminationStatus:
                browsertab.TerminationStatus.crashed,
            QWebEnginePage.KilledTerminationStatus:
                browsertab.TerminationStatus.killed,
            -1:
                browsertab.TerminationStatus.unknown,
        }
        self.renderer_process_terminated.emit(status_map[status], exitcode)

    @pyqtSlot(int)
    def _on_load_progress_workaround(self, perc):
        """Use loadProgress(100) to emit loadFinished(True).

        See https://bugreports.qt.io/browse/QTBUG-65223
        """
        if perc == 100 and self.load_status() != usertypes.LoadStatus.error:
            self._load_finished_fake.emit(True)

    @pyqtSlot(bool)
    def _on_load_finished_workaround(self, ok):
        """Use only loadFinished(False).

        See https://bugreports.qt.io/browse/QTBUG-65223
        """
        if not ok:
            self._load_finished_fake.emit(False)

    def _error_page_workaround(self, html):
        """Check if we're displaying a Chromium error page.

        This gets only called if we got loadFinished(False) without JavaScript,
        so we can display at least some error page.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-66643
        Needs to check the page content as a WORKAROUND for
        https://bugreports.qt.io/browse/QTBUG-66661
        """
        match = re.search(r'"errorCode":"([^"]*)"', html)
        if match is None:
            return
        self._show_error_page(self.url(), error=match.group(1))

    @pyqtSlot(bool)
    def _on_load_finished(self, ok):
        """Display a static error page if JavaScript is disabled."""
        super()._on_load_finished(ok)
        js_enabled = self.settings.test_attribute('content.javascript.enabled')
        if not ok and not js_enabled:
            self.dump_async(self._error_page_workaround)

        if ok and self._reload_url is not None:
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-66656
            log.config.debug(
                "Loading {} again because of config change".format(
                    self._reload_url.toDisplayString()))
            QTimer.singleShot(100, functools.partial(self.openurl,
                                                     self._reload_url,
                                                     predict=False))
            self._reload_url = None

        if not qtutils.version_check('5.10', compiled=False):
            # We can't do this when we have the loadFinished workaround as that
            # sometimes clears icons without loading a new page.
            # In general, this is handled by Qt, but when loading takes long,
            # the old icon is still displayed.
            self.icon_changed.emit(QIcon())

    @pyqtSlot(QUrl)
    def _on_predicted_navigation(self, url):
        """If we know we're going to visit an URL soon, change the settings."""
        super()._on_predicted_navigation(url)
        self.settings.update_for_url(url)

    @pyqtSlot(usertypes.NavigationRequest)
    def _on_navigation_request(self, navigation):
        super()._on_navigation_request(navigation)

        if qtutils.version_check('5.11.0', exact=True, compiled=False):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-68224
            layout = self._widget.layout()
            count = layout.count()
            children = self._widget.findChildren(QWidget)
            if not count and children:
                log.webview.warning("Found children not in layout: {}, "
                                    "focus proxy {} (QTBUG-68224)".format(
                                        children, self._widget.focusProxy()))
            if count > 1:
                log.webview.debug("Found {} widgets! (QTBUG-68224)"
                                  .format(count))
                for i in range(count):
                    item = layout.itemAt(i)
                    if item is None:
                        continue
                    widget = item.widget()
                    if widget is not self._widget.focusProxy():
                        log.webview.debug("Removing widget {} (QTBUG-68224)"
                                          .format(widget))
                        layout.removeWidget(widget)

        if not navigation.accepted or not navigation.is_main_frame:
            return

        settings_needing_reload = {
            'content.plugins',
            'content.javascript.enabled',
            'content.javascript.can_access_clipboard',
            'content.javascript.can_access_clipboard',
            'content.print_element_backgrounds',
            'input.spatial_navigation',
            'input.spatial_navigation',
        }
        assert settings_needing_reload.issubset(configdata.DATA)

        changed = self.settings.update_for_url(navigation.url)
        reload_needed = changed & settings_needing_reload

        # On Qt < 5.11, we don't don't need a reload when type == link_clicked.
        # On Qt 5.11.0, we always need a reload.
        # TODO on Qt > 5.11.0, we hopefully never need a reload:
        #      https://codereview.qt-project.org/#/c/229525/1
        if not qtutils.version_check('5.11.0', exact=True, compiled=False):
            if navigation.navigation_type != navigation.Type.link_clicked:
                reload_needed = False

        if reload_needed:
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-66656
            self._reload_url = navigation.url

    def _connect_signals(self):
        view = self._widget
        page = view.page()

        page.windowCloseRequested.connect(self.window_close_requested)
        page.linkHovered.connect(self.link_hovered)
        page.loadProgress.connect(self._on_load_progress)
        page.loadStarted.connect(self._on_load_started)
        page.certificate_error.connect(self._on_ssl_errors)
        page.authenticationRequired.connect(self._on_authentication_required)
        page.proxyAuthenticationRequired.connect(
            self._on_proxy_authentication_required)
        page.fullScreenRequested.connect(self._on_fullscreen_requested)
        page.contentsSizeChanged.connect(self.contents_size_changed)
        page.navigation_request.connect(self._on_navigation_request)

        view.titleChanged.connect(self.title_changed)
        view.urlChanged.connect(self._on_url_changed)
        view.renderProcessTerminated.connect(
            self._on_render_process_terminated)
        view.iconChanged.connect(self.icon_changed)
        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-65223
        if qtutils.version_check('5.10', compiled=False):
            page.loadProgress.connect(self._on_load_progress_workaround)
            self._load_finished_fake.connect(self._on_history_trigger)
            self._load_finished_fake.connect(self._restore_zoom)
            self._load_finished_fake.connect(self._on_load_finished)
            page.loadFinished.connect(self._on_load_finished_workaround)
        else:
            # for older Qt versions which break with the above
            page.loadProgress.connect(self._on_load_progress)
            page.loadFinished.connect(self._on_history_trigger)
            page.loadFinished.connect(self._restore_zoom)
            page.loadFinished.connect(self._on_load_finished)

        self.predicted_navigation.connect(self._on_predicted_navigation)

    def event_target(self):
        return self._widget.focusProxy()
