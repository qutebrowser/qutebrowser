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

"""Base class for a wrapper over QWebView/QWebEngineView."""

import enum
import itertools

import sip
import attr
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QUrl, QObject, QSizeF, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QApplication

from qutebrowser.keyinput import modeman
from qutebrowser.config import config
from qutebrowser.utils import (utils, objreg, usertypes, log, qtutils,
                               urlutils, message)
from qutebrowser.misc import miscwidgets, objects
from qutebrowser.browser import mouse, hints


tab_id_gen = itertools.count(0)


def create(win_id, private, parent=None):
    """Get a QtWebKit/QtWebEngine tab object.

    Args:
        win_id: The window ID where the tab will be shown.
        private: Whether the tab is a private/off the record tab.
        parent: The Qt parent to set.
    """
    # Importing modules here so we don't depend on QtWebEngine without the
    # argument and to avoid circular imports.
    mode_manager = modeman.instance(win_id)
    if objects.backend == usertypes.Backend.QtWebEngine:
        from qutebrowser.browser.webengine import webenginetab
        tab_class = webenginetab.WebEngineTab
    else:
        from qutebrowser.browser.webkit import webkittab
        tab_class = webkittab.WebKitTab
    return tab_class(win_id=win_id, mode_manager=mode_manager, private=private,
                     parent=parent)


def init():
    """Initialize backend-specific modules."""
    if objects.backend == usertypes.Backend.QtWebEngine:
        from qutebrowser.browser.webengine import webenginetab
        webenginetab.init()


class WebTabError(Exception):

    """Base class for various errors."""


class UnsupportedOperationError(WebTabError):

    """Raised when an operation is not supported with the given backend."""


TerminationStatus = enum.Enum('TerminationStatus', [
    'normal',
    'abnormal',  # non-zero exit status
    'crashed',   # e.g. segfault
    'killed',
    'unknown',
])


@attr.s
class TabData:

    """A simple namespace with a fixed set of attributes.

    Attributes:
        keep_icon: Whether the (e.g. cloned) icon should not be cleared on page
                   load.
        inspector: The QWebInspector used for this webview.
        open_target: Where to open the next link.
                     Only used for QtWebKit.
        override_target: Override for open_target for fake clicks (like hints).
                         Only used for QtWebKit.
        pinned: Flag to pin the tab.
        fullscreen: Whether the tab has a video shown fullscreen currently.
        netrc_used: Whether netrc authentication was performed.
        input_mode: current input mode for the tab.
    """

    keep_icon = attr.ib(False)
    inspector = attr.ib(None)
    open_target = attr.ib(usertypes.ClickTarget.normal)
    override_target = attr.ib(None)
    pinned = attr.ib(False)
    fullscreen = attr.ib(False)
    netrc_used = attr.ib(False)
    input_mode = attr.ib(usertypes.KeyMode.normal)

    def should_show_icon(self):
        return (config.val.tabs.favicons.show == 'always' or
                config.val.tabs.favicons.show == 'pinned' and self.pinned)


class AbstractAction:

    """Attribute of AbstractTab for Qt WebActions.

    Class attributes (overridden by subclasses):
        action_class: The class actions are defined on (QWeb{Engine,}Page)
        action_base: The type of the actions (QWeb{Engine,}Page.WebAction)
    """

    action_class = None
    action_base = None

    def __init__(self, tab):
        self._widget = None
        self._tab = tab

    def exit_fullscreen(self):
        """Exit the fullscreen mode."""
        raise NotImplementedError

    def save_page(self):
        """Save the current page."""
        raise NotImplementedError

    def run_string(self, name):
        """Run a webaction based on its name."""
        member = getattr(self.action_class, name, None)
        if not isinstance(member, self.action_base):
            raise WebTabError("{} is not a valid web action!".format(name))
        self._widget.triggerPageAction(member)

    def show_source(self):
        """Show the source of the current page in a new tab."""
        raise NotImplementedError


class AbstractPrinting:

    """Attribute of AbstractTab for printing the page."""

    def __init__(self):
        self._widget = None

    def check_pdf_support(self):
        raise NotImplementedError

    def check_printer_support(self):
        raise NotImplementedError

    def check_preview_support(self):
        raise NotImplementedError

    def to_pdf(self, filename):
        raise NotImplementedError

    def to_printer(self, printer, callback=None):
        """Print the tab.

        Args:
            printer: The QPrinter to print to.
            callback: Called with a boolean
                      (True if printing succeeded, False otherwise)
        """
        raise NotImplementedError


class AbstractSearch(QObject):

    """Attribute of AbstractTab for doing searches.

    Attributes:
        text: The last thing this view was searched for.
        search_displayed: Whether we're currently displaying search results in
                          this view.
        _flags: The flags of the last search (needs to be set by subclasses).
        _widget: The underlying WebView widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget = None
        self.text = None
        self.search_displayed = False

    def _is_case_sensitive(self, ignore_case):
        """Check if case-sensitivity should be used.

        This assumes self.text is already set properly.

        Arguments:
            ignore_case: The ignore_case value from the config.
        """
        mapping = {
            'smart': not self.text.islower(),
            'never': True,
            'always': False,
        }
        return mapping[ignore_case]

    def search(self, text, *, ignore_case='never', reverse=False,
               result_cb=None):
        """Find the given text on the page.

        Args:
            text: The text to search for.
            ignore_case: Search case-insensitively. ('always'/'never/'smart')
            reverse: Reverse search direction.
            result_cb: Called with a bool indicating whether a match was found.
        """
        raise NotImplementedError

    def clear(self):
        """Clear the current search."""
        raise NotImplementedError

    def prev_result(self, *, result_cb=None):
        """Go to the previous result of the current search.

        Args:
            result_cb: Called with a bool indicating whether a match was found.
        """
        raise NotImplementedError

    def next_result(self, *, result_cb=None):
        """Go to the next result of the current search.

        Args:
            result_cb: Called with a bool indicating whether a match was found.
        """
        raise NotImplementedError


class AbstractZoom(QObject):

    """Attribute of AbstractTab for controlling zoom.

    Attributes:
        _neighborlist: A NeighborList with the zoom levels.
        _default_zoom_changed: Whether the zoom was changed from the default.
    """

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._widget = None
        self._default_zoom_changed = False
        self._init_neighborlist()
        config.instance.changed.connect(self._on_config_changed)
        self._zoom_factor = float(config.val.zoom.default) / 100

        # # FIXME:qtwebengine is this needed?
        # # For some reason, this signal doesn't get disconnected automatically
        # # when the WebView is destroyed on older PyQt versions.
        # # See https://github.com/qutebrowser/qutebrowser/issues/390
        # self.destroyed.connect(functools.partial(
        #     cfg.changed.disconnect, self.init_neighborlist))

    @pyqtSlot(str)
    def _on_config_changed(self, option):
        if option in ['zoom.levels', 'zoom.default']:
            if not self._default_zoom_changed:
                factor = float(config.val.zoom.default) / 100
                self.set_factor(factor)
            self._init_neighborlist()

    def _init_neighborlist(self):
        """Initialize self._neighborlist."""
        levels = config.val.zoom.levels
        self._neighborlist = usertypes.NeighborList(
            levels, mode=usertypes.NeighborList.Modes.edge)
        self._neighborlist.fuzzyval = config.val.zoom.default

    def offset(self, offset):
        """Increase/Decrease the zoom level by the given offset.

        Args:
            offset: The offset in the zoom level list.

        Return:
            The new zoom percentage.
        """
        level = self._neighborlist.getitem(offset)
        self.set_factor(float(level) / 100, fuzzyval=False)
        return level

    def _set_factor_internal(self, factor):
        raise NotImplementedError

    def set_factor(self, factor, *, fuzzyval=True):
        """Zoom to a given zoom factor.

        Args:
            factor: The zoom factor as float.
            fuzzyval: Whether to set the NeighborLists fuzzyval.
        """
        if fuzzyval:
            self._neighborlist.fuzzyval = int(factor * 100)
        if factor < 0:
            raise ValueError("Can't zoom to factor {}!".format(factor))

        default_zoom_factor = float(config.val.zoom.default) / 100
        self._default_zoom_changed = (factor != default_zoom_factor)

        self._zoom_factor = factor
        self._set_factor_internal(factor)

    def factor(self):
        return self._zoom_factor

    def set_default(self):
        self._set_factor_internal(float(config.val.zoom.default) / 100)

    def set_current(self):
        self._set_factor_internal(self._zoom_factor)


class AbstractCaret(QObject):

    """Attribute of AbstractTab for caret browsing.

    Signals:
        selection_toggled: Emitted when the selection was toggled.
                           arg: Whether the selection is now active.
    """

    selection_toggled = pyqtSignal(bool)

    def __init__(self, tab, mode_manager, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._widget = None
        self.selection_enabled = False
        mode_manager.entered.connect(self._on_mode_entered)
        mode_manager.left.connect(self._on_mode_left)

    def _on_mode_entered(self, mode):
        raise NotImplementedError

    def _on_mode_left(self, mode):
        raise NotImplementedError

    def move_to_next_line(self, count=1):
        raise NotImplementedError

    def move_to_prev_line(self, count=1):
        raise NotImplementedError

    def move_to_next_char(self, count=1):
        raise NotImplementedError

    def move_to_prev_char(self, count=1):
        raise NotImplementedError

    def move_to_end_of_word(self, count=1):
        raise NotImplementedError

    def move_to_next_word(self, count=1):
        raise NotImplementedError

    def move_to_prev_word(self, count=1):
        raise NotImplementedError

    def move_to_start_of_line(self):
        raise NotImplementedError

    def move_to_end_of_line(self):
        raise NotImplementedError

    def move_to_start_of_next_block(self, count=1):
        raise NotImplementedError

    def move_to_start_of_prev_block(self, count=1):
        raise NotImplementedError

    def move_to_end_of_next_block(self, count=1):
        raise NotImplementedError

    def move_to_end_of_prev_block(self, count=1):
        raise NotImplementedError

    def move_to_start_of_document(self):
        raise NotImplementedError

    def move_to_end_of_document(self):
        raise NotImplementedError

    def toggle_selection(self):
        raise NotImplementedError

    def drop_selection(self):
        raise NotImplementedError

    def selection(self, callback):
        raise NotImplementedError

    def follow_selected(self, *, tab=False):
        raise NotImplementedError


class AbstractScroller(QObject):

    """Attribute of AbstractTab to manage scroll position."""

    perc_changed = pyqtSignal(int, int)

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._widget = None
        self.perc_changed.connect(self._log_scroll_pos_change)

    @pyqtSlot()
    def _log_scroll_pos_change(self):
        log.webview.vdebug("Scroll position changed to {}".format(
            self.pos_px()))

    def _init_widget(self, widget):
        self._widget = widget

    def pos_px(self):
        raise NotImplementedError

    def pos_perc(self):
        raise NotImplementedError

    def to_perc(self, x=None, y=None):
        raise NotImplementedError

    def to_point(self, point):
        raise NotImplementedError

    def to_anchor(self, name):
        raise NotImplementedError

    def delta(self, x=0, y=0):
        raise NotImplementedError

    def delta_page(self, x=0, y=0):
        raise NotImplementedError

    def up(self, count=1):
        raise NotImplementedError

    def down(self, count=1):
        raise NotImplementedError

    def left(self, count=1):
        raise NotImplementedError

    def right(self, count=1):
        raise NotImplementedError

    def top(self):
        raise NotImplementedError

    def bottom(self):
        raise NotImplementedError

    def page_up(self, count=1):
        raise NotImplementedError

    def page_down(self, count=1):
        raise NotImplementedError

    def at_top(self):
        raise NotImplementedError

    def at_bottom(self):
        raise NotImplementedError


class AbstractHistory:

    """The history attribute of a AbstractTab."""

    def __init__(self, tab):
        self._tab = tab
        self._history = None

    def __len__(self):
        return len(self._history)

    def __iter__(self):
        return iter(self._history.items())

    def current_idx(self):
        raise NotImplementedError

    def back(self, count=1):
        """Go back in the tab's history."""
        idx = self.current_idx() - count
        if idx >= 0:
            self._go_to_item(self._item_at(idx))
        else:
            self._go_to_item(self._item_at(0))
            raise WebTabError("At beginning of history.")

    def forward(self, count=1):
        """Go forward in the tab's history."""
        idx = self.current_idx() + count
        if idx < len(self):
            self._go_to_item(self._item_at(idx))
        else:
            self._go_to_item(self._item_at(len(self) - 1))
            raise WebTabError("At end of history.")

    def can_go_back(self):
        raise NotImplementedError

    def can_go_forward(self):
        raise NotImplementedError

    def _item_at(self, i):
        raise NotImplementedError

    def _go_to_item(self, item):
        raise NotImplementedError

    def serialize(self):
        """Serialize into an opaque format understood by self.deserialize."""
        raise NotImplementedError

    def deserialize(self, data):
        """Serialize from a format produced by self.serialize."""
        raise NotImplementedError

    def load_items(self, items):
        """Deserialize from a list of WebHistoryItems."""
        raise NotImplementedError


class AbstractElements:

    """Finding and handling of elements on the page."""

    def __init__(self, tab):
        self._widget = None
        self._tab = tab

    def find_css(self, selector, callback, *, only_visible=False):
        """Find all HTML elements matching a given selector async.

        Args:
            callback: The callback to be called when the search finished.
            selector: The CSS selector to search for.
            only_visible: Only show elements which are visible on screen.
        """
        raise NotImplementedError

    def find_id(self, elem_id, callback):
        """Find the HTML element with the given ID async.

        Args:
            callback: The callback to be called when the search finished.
            elem_id: The ID to search for.
        """
        raise NotImplementedError

    def find_focused(self, callback):
        """Find the focused element on the page async.

        Args:
            callback: The callback to be called when the search finished.
                      Called with a WebEngineElement or None.
        """
        raise NotImplementedError

    def find_at_pos(self, pos, callback):
        """Find the element at the given position async.

        This is also called "hit test" elsewhere.

        Args:
            pos: The QPoint to get the element for.
            callback: The callback to be called when the search finished.
                      Called with a WebEngineElement or None.
        """
        raise NotImplementedError


class AbstractTab(QWidget):

    """A wrapper over the given widget to hide its API and expose another one.

    We use this to unify QWebView and QWebEngineView.

    Attributes:
        history: The AbstractHistory for the current tab.
        registry: The ObjectRegistry associated with this tab.
        private: Whether private browsing is turned on for this tab.

        _load_status: loading status of this page
                      Accessible via load_status() method.
        _has_ssl_errors: Whether SSL errors happened.
                         Needs to be set by subclasses.

        for properties, see WebView/WebEngineView docs.

    Signals:
        See related Qt signals.

        new_tab_requested: Emitted when a new tab should be opened with the
                           given URL.
        load_status_changed: The loading status changed
        fullscreen_requested: Fullscreen display was requested by the page.
                              arg: True if fullscreen should be turned on,
                                   False if it should be turned off.
        renderer_process_terminated: Emitted when the underlying renderer
                                     process terminated.
                                     arg 0: A TerminationStatus member.
                                     arg 1: The exit code.
        predicted_navigation: Emitted before we tell Qt to open a URL.
    """

    window_close_requested = pyqtSignal()
    link_hovered = pyqtSignal(str)
    load_started = pyqtSignal()
    load_progress = pyqtSignal(int)
    load_finished = pyqtSignal(bool)
    icon_changed = pyqtSignal(QIcon)
    title_changed = pyqtSignal(str)
    load_status_changed = pyqtSignal(str)
    new_tab_requested = pyqtSignal(QUrl)
    url_changed = pyqtSignal(QUrl)
    shutting_down = pyqtSignal()
    contents_size_changed = pyqtSignal(QSizeF)
    add_history_item = pyqtSignal(QUrl, QUrl, str)  # url, requested url, title
    fullscreen_requested = pyqtSignal(bool)
    renderer_process_terminated = pyqtSignal(TerminationStatus, int)
    predicted_navigation = pyqtSignal(QUrl)

    def __init__(self, *, win_id, mode_manager, private, parent=None):
        self.private = private
        self.win_id = win_id
        self.tab_id = next(tab_id_gen)
        super().__init__(parent)

        self.registry = objreg.ObjectRegistry()
        tab_registry = objreg.get('tab-registry', scope='window',
                                  window=win_id)
        tab_registry[self.tab_id] = self
        objreg.register('tab', self, registry=self.registry)

        self.data = TabData()
        self._layout = miscwidgets.WrapperLayout(self)
        self._widget = None
        self._progress = 0
        self._has_ssl_errors = False
        self._mode_manager = mode_manager
        self._load_status = usertypes.LoadStatus.none
        self._mouse_event_filter = mouse.MouseEventFilter(
            self, parent=self)
        self.backend = None

        # FIXME:qtwebengine  Should this be public api via self.hints?
        #                    Also, should we get it out of objreg?
        hintmanager = hints.HintManager(win_id, self.tab_id, parent=self)
        objreg.register('hintmanager', hintmanager, scope='tab',
                        window=self.win_id, tab=self.tab_id)

        self.predicted_navigation.connect(self._on_predicted_navigation)

    def _set_widget(self, widget):
        # pylint: disable=protected-access
        self._widget = widget
        self._layout.wrap(self, widget)
        self.history._history = widget.history()
        self.scroller._init_widget(widget)
        self.caret._widget = widget
        self.zoom._widget = widget
        self.search._widget = widget
        self.printing._widget = widget
        self.action._widget = widget
        self.elements._widget = widget
        self.settings._settings = widget.settings()

        self._install_event_filter()
        self.zoom.set_default()

    def _install_event_filter(self):
        raise NotImplementedError

    def _set_load_status(self, val):
        """Setter for load_status."""
        if not isinstance(val, usertypes.LoadStatus):
            raise TypeError("Type {} is no LoadStatus member!".format(val))
        log.webview.debug("load status for {}: {}".format(repr(self), val))
        self._load_status = val
        self.load_status_changed.emit(val.name)

    def event_target(self):
        """Return the widget events should be sent to."""
        raise NotImplementedError

    def send_event(self, evt):
        """Send the given event to the underlying widget.

        The event will be sent via QApplication.postEvent.
        Note that a posted event may not be re-used in any way!
        """
        # This only gives us some mild protection against re-using events, but
        # it's certainly better than a segfault.
        if getattr(evt, 'posted', False):
            raise utils.Unreachable("Can't re-use an event which was already "
                                    "posted!")

        recipient = self.event_target()
        if recipient is None:
            # https://github.com/qutebrowser/qutebrowser/issues/3888
            log.webview.warning("Unable to find event target!")
            return

        evt.posted = True
        QApplication.postEvent(recipient, evt)

    @pyqtSlot(QUrl)
    def _on_predicted_navigation(self, url):
        """Adjust the title if we are going to visit an URL soon."""
        qtutils.ensure_valid(url)
        url_string = url.toDisplayString()
        log.webview.debug("Predicted navigation: {}".format(url_string))
        self.title_changed.emit(url_string)

    @pyqtSlot(QUrl)
    def _on_url_changed(self, url):
        """Update title when URL has changed and no title is available."""
        if url.isValid() and not self.title():
            self.title_changed.emit(url.toDisplayString())
        self.url_changed.emit(url)

    @pyqtSlot()
    def _on_load_started(self):
        self._progress = 0
        self._has_ssl_errors = False
        self._set_load_status(usertypes.LoadStatus.loading)
        self.load_started.emit()

    @pyqtSlot(usertypes.NavigationRequest)
    def _on_navigation_request(self, navigation):
        """Handle common acceptNavigationRequest code."""
        url = utils.elide(navigation.url.toDisplayString(), 100)
        log.webview.debug("navigation request: url {}, type {}, is_main_frame "
                          "{}".format(url,
                                      navigation.navigation_type,
                                      navigation.is_main_frame))

        if (navigation.navigation_type == navigation.Type.link_clicked and
                not navigation.url.isValid()):
            msg = urlutils.get_errstring(navigation.url,
                                         "Invalid link clicked")
            message.error(msg)
            self.data.open_target = usertypes.ClickTarget.normal
            navigation.accepted = False

    def handle_auto_insert_mode(self, ok):
        """Handle `input.insert_mode.auto_load` after loading finished."""
        if not config.val.input.insert_mode.auto_load or not ok:
            return

        cur_mode = self._mode_manager.mode
        if cur_mode == usertypes.KeyMode.insert:
            return

        def _auto_insert_mode_cb(elem):
            """Called from JS after finding the focused element."""
            if elem is None:
                log.webview.debug("No focused element!")
                return
            if elem.is_editable():
                modeman.enter(self.win_id, usertypes.KeyMode.insert,
                              'load finished', only_if_normal=True)

        self.elements.find_focused(_auto_insert_mode_cb)

    @pyqtSlot(bool)
    def _on_load_finished(self, ok):
        if sip.isdeleted(self._widget):
            # https://github.com/qutebrowser/qutebrowser/issues/3498
            return

        sess_manager = objreg.get('session-manager')
        sess_manager.save_autosave()

        if ok and not self._has_ssl_errors:
            if self.url().scheme() == 'https':
                self._set_load_status(usertypes.LoadStatus.success_https)
            else:
                self._set_load_status(usertypes.LoadStatus.success)
        elif ok:
            self._set_load_status(usertypes.LoadStatus.warn)
        else:
            self._set_load_status(usertypes.LoadStatus.error)

        self.load_finished.emit(ok)

        if not self.title():
            self.title_changed.emit(self.url().toDisplayString())

        self.zoom.set_current()

    @pyqtSlot()
    def _on_history_trigger(self):
        """Emit add_history_item when triggered by backend-specific signal."""
        raise NotImplementedError

    @pyqtSlot(int)
    def _on_load_progress(self, perc):
        self._progress = perc
        self.load_progress.emit(perc)

    @pyqtSlot()
    def _on_ssl_errors(self):
        self._has_ssl_errors = True

    def url(self, requested=False):
        raise NotImplementedError

    def progress(self):
        return self._progress

    def load_status(self):
        return self._load_status

    def _openurl_prepare(self, url, *, predict=True):
        qtutils.ensure_valid(url)
        if predict:
            self.predicted_navigation.emit(url)

    def openurl(self, url, *, predict=True):
        raise NotImplementedError

    def reload(self, *, force=False):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def clear_ssl_errors(self):
        raise NotImplementedError

    def key_press(self, key, modifier=Qt.NoModifier):
        """Send a fake key event to this tab."""
        raise NotImplementedError

    def dump_async(self, callback, *, plain=False):
        """Dump the current page's html asynchronously.

        The given callback will be called with the result when dumping is
        complete.
        """
        raise NotImplementedError

    def run_js_async(self, code, callback=None, *, world=None):
        """Run javascript async.

        The given callback will be called with the result when running JS is
        complete.

        Args:
            code: The javascript code to run.
            callback: The callback to call with the result, or None.
            world: A world ID (int or usertypes.JsWorld member) to run the JS
                   in the main world or in another isolated world.
        """
        raise NotImplementedError

    def shutdown(self):
        raise NotImplementedError

    def title(self):
        raise NotImplementedError

    def icon(self):
        raise NotImplementedError

    def set_html(self, html, base_url=QUrl()):
        raise NotImplementedError

    def networkaccessmanager(self):
        """Get the QNetworkAccessManager for this tab.

        This is only implemented for QtWebKit.
        For QtWebEngine, always returns None.
        """
        raise NotImplementedError

    def user_agent(self):
        """Get the user agent for this tab.

        This is only implemented for QtWebKit.
        For QtWebEngine, always returns None.
        """
        raise NotImplementedError

    def __repr__(self):
        try:
            url = utils.elide(self.url().toDisplayString(QUrl.EncodeUnicode),
                              100)
        except (AttributeError, RuntimeError) as exc:
            url = '<{}>'.format(exc.__class__.__name__)
        return utils.get_repr(self, tab_id=self.tab_id, url=url)

    def is_deleted(self):
        return sip.isdeleted(self._widget)
