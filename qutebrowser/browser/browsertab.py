# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import functools
import typing

import attr
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QUrl, QObject, QSizeF, Qt,
                          QEvent, QPoint)
from PyQt5.QtGui import QKeyEvent, QIcon
from PyQt5.QtWidgets import QWidget, QApplication, QDialog
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
from PyQt5.QtNetwork import QNetworkAccessManager

if typing.TYPE_CHECKING:
    from PyQt5.QtWebKit import QWebHistory
    from PyQt5.QtWebEngineWidgets import QWebEngineHistory

import pygments
import pygments.lexers
import pygments.formatters

from qutebrowser.keyinput import modeman
from qutebrowser.config import config
from qutebrowser.utils import (utils, objreg, usertypes, log, qtutils,
                               urlutils, message)
from qutebrowser.misc import miscwidgets, objects, sessions
from qutebrowser.browser import eventfilter
from qutebrowser.qt import sip

if typing.TYPE_CHECKING:
    from qutebrowser.browser import webelem
    from qutebrowser.browser.inspector import AbstractWebInspector


tab_id_gen = itertools.count(0)


def create(win_id: int,
           private: bool,
           parent: QWidget = None) -> 'AbstractTab':
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
        tab_class = webenginetab.WebEngineTab  # type: typing.Type[AbstractTab]
    else:
        from qutebrowser.browser.webkit import webkittab
        tab_class = webkittab.WebKitTab
    return tab_class(win_id=win_id, mode_manager=mode_manager, private=private,
                     parent=parent)


def init() -> None:
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
        viewing_source: Set if we're currently showing a source view.
                        Only used when sources are shown via pygments.
        open_target: Where to open the next link.
                     Only used for QtWebKit.
        override_target: Override for open_target for fake clicks (like hints).
                         Only used for QtWebKit.
        pinned: Flag to pin the tab.
        fullscreen: Whether the tab has a video shown fullscreen currently.
        netrc_used: Whether netrc authentication was performed.
        input_mode: current input mode for the tab.
    """

    keep_icon = attr.ib(False)  # type: bool
    viewing_source = attr.ib(False)  # type: bool
    inspector = attr.ib(None)  # type: typing.Optional[AbstractWebInspector]
    open_target = attr.ib(
        usertypes.ClickTarget.normal)  # type: usertypes.ClickTarget
    override_target = attr.ib(
        None)  # type: typing.Optional[usertypes.ClickTarget]
    pinned = attr.ib(False)  # type: bool
    fullscreen = attr.ib(False)  # type: bool
    netrc_used = attr.ib(False)  # type: bool
    input_mode = attr.ib(usertypes.KeyMode.normal)  # type: usertypes.KeyMode
    last_navigation = attr.ib(None)  # type: usertypes.NavigationRequest

    def should_show_icon(self) -> bool:
        return (config.val.tabs.favicons.show == 'always' or
                config.val.tabs.favicons.show == 'pinned' and self.pinned)


class AbstractAction:

    """Attribute ``action`` of AbstractTab for Qt WebActions."""

    # The class actions are defined on (QWeb{Engine,}Page)
    action_class = None  # type: type
    # The type of the actions (QWeb{Engine,}Page.WebAction)
    action_base = None  # type: type

    def __init__(self, tab: 'AbstractTab') -> None:
        self._widget = typing.cast(QWidget, None)
        self._tab = tab

    def exit_fullscreen(self) -> None:
        """Exit the fullscreen mode."""
        raise NotImplementedError

    def save_page(self) -> None:
        """Save the current page."""
        raise NotImplementedError

    def run_string(self, name: str) -> None:
        """Run a webaction based on its name."""
        member = getattr(self.action_class, name, None)
        if not isinstance(member, self.action_base):
            raise WebTabError("{} is not a valid web action!".format(name))
        self._widget.triggerPageAction(member)

    def show_source(
            self,
            pygments: bool = False  # pylint: disable=redefined-outer-name
    ) -> None:
        """Show the source of the current page in a new tab."""
        raise NotImplementedError

    def _show_source_pygments(self) -> None:

        def show_source_cb(source: str) -> None:
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
            new_tab.set_html(highlighted, self._tab.url())
            new_tab.data.viewing_source = True

        self._tab.dump_async(show_source_cb)


class AbstractPrinting:

    """Attribute ``printing`` of AbstractTab for printing the page."""

    def __init__(self, tab: 'AbstractTab') -> None:
        self._widget = typing.cast(QWidget, None)
        self._tab = tab

    def check_pdf_support(self) -> None:
        """Check whether writing to PDFs is supported.

        If it's not supported (by the current Qt version), a WebTabError is
        raised.
        """
        raise NotImplementedError

    def check_printer_support(self) -> None:
        """Check whether writing to a printer is supported.

        If it's not supported (by the current Qt version), a WebTabError is
        raised.
        """
        raise NotImplementedError

    def check_preview_support(self) -> None:
        """Check whether showing a print preview is supported.

        If it's not supported (by the current Qt version), a WebTabError is
        raised.
        """
        raise NotImplementedError

    def to_pdf(self, filename: str) -> bool:
        """Print the tab to a PDF with the given filename."""
        raise NotImplementedError

    def to_printer(self, printer: QPrinter,
                   callback: typing.Callable[[bool], None] = None) -> None:
        """Print the tab.

        Args:
            printer: The QPrinter to print to.
            callback: Called with a boolean
                      (True if printing succeeded, False otherwise)
        """
        raise NotImplementedError

    def show_dialog(self) -> None:
        """Print with a QPrintDialog."""
        self.check_printer_support()

        def print_callback(ok: bool) -> None:
            """Called when printing finished."""
            if not ok:
                message.error("Printing failed!")
            diag.deleteLater()

        def do_print() -> None:
            """Called when the dialog was closed."""
            self.to_printer(diag.printer(), print_callback)

        diag = QPrintDialog(self._tab)
        if utils.is_mac:
            # For some reason we get a segfault when using open() on macOS
            ret = diag.exec_()
            if ret == QDialog.Accepted:
                do_print()
        else:
            diag.open(do_print)


class AbstractSearch(QObject):

    """Attribute ``search`` of AbstractTab for doing searches.

    Attributes:
        text: The last thing this view was searched for.
        search_displayed: Whether we're currently displaying search results in
                          this view.
        _flags: The flags of the last search (needs to be set by subclasses).
        _widget: The underlying WebView widget.
    """

    #: Signal emitted when a search was finished
    #: (True if the text was found, False otherwise)
    finished = pyqtSignal(bool)
    #: Signal emitted when an existing search was cleared.
    cleared = pyqtSignal()

    _Callback = typing.Callable[[bool], None]

    def __init__(self, tab: 'AbstractTab', parent: QWidget = None):
        super().__init__(parent)
        self._tab = tab
        self._widget = typing.cast(QWidget, None)
        self.text = None  # type: typing.Optional[str]
        self.search_displayed = False

    def _is_case_sensitive(self, ignore_case: usertypes.IgnoreCase) -> bool:
        """Check if case-sensitivity should be used.

        This assumes self.text is already set properly.

        Arguments:
            ignore_case: The ignore_case value from the config.
        """
        assert self.text is not None
        mapping = {
            usertypes.IgnoreCase.smart: not self.text.islower(),
            usertypes.IgnoreCase.never: True,
            usertypes.IgnoreCase.always: False,
        }
        return mapping[ignore_case]

    def search(self, text: str, *,
               ignore_case: usertypes.IgnoreCase = usertypes.IgnoreCase.never,
               reverse: bool = False,
               wrap: bool = True,
               result_cb: _Callback = None) -> None:
        """Find the given text on the page.

        Args:
            text: The text to search for.
            ignore_case: Search case-insensitively.
            reverse: Reverse search direction.
            wrap: Allow wrapping at the top or bottom of the page.
            result_cb: Called with a bool indicating whether a match was found.
        """
        raise NotImplementedError

    def clear(self) -> None:
        """Clear the current search."""
        raise NotImplementedError

    def prev_result(self, *, result_cb: _Callback = None) -> None:
        """Go to the previous result of the current search.

        Args:
            result_cb: Called with a bool indicating whether a match was found.
        """
        raise NotImplementedError

    def next_result(self, *, result_cb: _Callback = None) -> None:
        """Go to the next result of the current search.

        Args:
            result_cb: Called with a bool indicating whether a match was found.
        """
        raise NotImplementedError


class AbstractZoom(QObject):

    """Attribute ``zoom`` of AbstractTab for controlling zoom."""

    def __init__(self, tab: 'AbstractTab', parent: QWidget = None) -> None:
        super().__init__(parent)
        self._tab = tab
        self._widget = typing.cast(QWidget, None)
        # Whether zoom was changed from the default.
        self._default_zoom_changed = False
        self._init_neighborlist()
        config.instance.changed.connect(self._on_config_changed)
        self._zoom_factor = float(config.val.zoom.default) / 100

    @pyqtSlot(str)
    def _on_config_changed(self, option: str) -> None:
        if option in ['zoom.levels', 'zoom.default']:
            if not self._default_zoom_changed:
                factor = float(config.val.zoom.default) / 100
                self.set_factor(factor)
            self._init_neighborlist()

    def _init_neighborlist(self) -> None:
        """Initialize self._neighborlist.

        It is a NeighborList with the zoom levels."""
        levels = config.val.zoom.levels
        self._neighborlist = usertypes.NeighborList(
            levels, mode=usertypes.NeighborList.Modes.edge
        )  # type: usertypes.NeighborList[float]
        self._neighborlist.fuzzyval = config.val.zoom.default

    def apply_offset(self, offset: int) -> float:
        """Increase/Decrease the zoom level by the given offset.

        Args:
            offset: The offset in the zoom level list.

        Return:
            The new zoom level.
        """
        level = self._neighborlist.getitem(offset)
        self.set_factor(float(level) / 100, fuzzyval=False)
        return level

    def _set_factor_internal(self, factor: float) -> None:
        raise NotImplementedError

    def set_factor(self, factor: float, *, fuzzyval: bool = True) -> None:
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

    def factor(self) -> float:
        return self._zoom_factor

    def apply_default(self) -> None:
        self._set_factor_internal(float(config.val.zoom.default) / 100)

    def reapply(self) -> None:
        self._set_factor_internal(self._zoom_factor)


class SelectionState(enum.Enum):

    """Possible states of selection in caret mode.

    NOTE: Names need to line up with SelectionState in caret.js!
    """

    none = 1
    normal = 2
    line = 3


class AbstractCaret(QObject):

    """Attribute ``caret`` of AbstractTab for caret browsing."""

    #: Signal emitted when the selection was toggled.
    selection_toggled = pyqtSignal(SelectionState)
    #: Emitted when a ``follow_selection`` action is done.
    follow_selected_done = pyqtSignal()

    def __init__(self,
                 mode_manager: modeman.ModeManager,
                 parent: QWidget = None) -> None:
        super().__init__(parent)
        self._widget = typing.cast(QWidget, None)
        self._mode_manager = mode_manager
        mode_manager.entered.connect(self._on_mode_entered)
        mode_manager.left.connect(self._on_mode_left)
        # self._tab is set by subclasses so mypy knows its concrete type.

    def _on_mode_entered(self, mode: usertypes.KeyMode) -> None:
        raise NotImplementedError

    def _on_mode_left(self, mode: usertypes.KeyMode) -> None:
        raise NotImplementedError

    def move_to_next_line(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_prev_line(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_next_char(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_prev_char(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_end_of_word(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_next_word(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_prev_word(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_start_of_line(self) -> None:
        raise NotImplementedError

    def move_to_end_of_line(self) -> None:
        raise NotImplementedError

    def move_to_start_of_next_block(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_start_of_prev_block(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_end_of_next_block(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_end_of_prev_block(self, count: int = 1) -> None:
        raise NotImplementedError

    def move_to_start_of_document(self) -> None:
        raise NotImplementedError

    def move_to_end_of_document(self) -> None:
        raise NotImplementedError

    def toggle_selection(self, line: bool = False) -> None:
        raise NotImplementedError

    def drop_selection(self) -> None:
        raise NotImplementedError

    def selection(self, callback: typing.Callable[[str], None]) -> None:
        raise NotImplementedError

    def reverse_selection(self) -> None:
        raise NotImplementedError

    def _follow_enter(self, tab: bool) -> None:
        """Follow a link by faking an enter press."""
        if tab:
            self._tab.fake_key_press(Qt.Key_Enter, modifier=Qt.ControlModifier)
        else:
            self._tab.fake_key_press(Qt.Key_Enter)

    def follow_selected(self, *, tab: bool = False) -> None:
        raise NotImplementedError


class AbstractScroller(QObject):

    """Attribute ``scroller`` of AbstractTab to manage scroll position."""

    #: Signal emitted when the scroll position changed (int, int)
    perc_changed = pyqtSignal(int, int)
    #: Signal emitted before the user requested a jump.
    #: Used to set the special ' mark so the user can return.
    before_jump_requested = pyqtSignal()

    def __init__(self, tab: 'AbstractTab', parent: QWidget = None):
        super().__init__(parent)
        self._tab = tab
        self._widget = typing.cast(QWidget, None)
        if 'log-scroll-pos' in objects.debug_flags:
            self.perc_changed.connect(self._log_scroll_pos_change)

    @pyqtSlot()
    def _log_scroll_pos_change(self) -> None:
        log.webview.vdebug(  # type: ignore[attr-defined]
            "Scroll position changed to {}".format(self.pos_px()))

    def _init_widget(self, widget: QWidget) -> None:
        self._widget = widget

    def pos_px(self) -> int:
        raise NotImplementedError

    def pos_perc(self) -> int:
        raise NotImplementedError

    def to_perc(self, x: int = None, y: int = None) -> None:
        raise NotImplementedError

    def to_point(self, point: QPoint) -> None:
        raise NotImplementedError

    def to_anchor(self, name: str) -> None:
        raise NotImplementedError

    def delta(self, x: int = 0, y: int = 0) -> None:
        raise NotImplementedError

    def delta_page(self, x: float = 0, y: float = 0) -> None:
        raise NotImplementedError

    def up(self, count: int = 1) -> None:
        raise NotImplementedError

    def down(self, count: int = 1) -> None:
        raise NotImplementedError

    def left(self, count: int = 1) -> None:
        raise NotImplementedError

    def right(self, count: int = 1) -> None:
        raise NotImplementedError

    def top(self) -> None:
        raise NotImplementedError

    def bottom(self) -> None:
        raise NotImplementedError

    def page_up(self, count: int = 1) -> None:
        raise NotImplementedError

    def page_down(self, count: int = 1) -> None:
        raise NotImplementedError

    def at_top(self) -> bool:
        raise NotImplementedError

    def at_bottom(self) -> bool:
        raise NotImplementedError


class AbstractHistoryPrivate:

    """Private API related to the history."""

    def __init__(self, tab: 'AbstractTab'):
        self._tab = tab
        self._history = typing.cast(
            typing.Union['QWebHistory', 'QWebEngineHistory'], None)

    def serialize(self) -> bytes:
        """Serialize into an opaque format understood by self.deserialize."""
        raise NotImplementedError

    def deserialize(self, data: bytes) -> None:
        """Deserialize from a format produced by self.serialize."""
        raise NotImplementedError

    def load_items(self, items: typing.Sequence) -> None:
        """Deserialize from a list of WebHistoryItems."""
        raise NotImplementedError


class AbstractHistory:

    """The history attribute of a AbstractTab."""

    def __init__(self, tab: 'AbstractTab') -> None:
        self._tab = tab
        self._history = typing.cast(
            typing.Union['QWebHistory', 'QWebEngineHistory'], None)
        self.private_api = AbstractHistoryPrivate(tab)

    def __len__(self) -> int:
        raise NotImplementedError

    def __iter__(self) -> typing.Iterable:
        raise NotImplementedError

    def _check_count(self, count: int) -> None:
        """Check whether the count is positive."""
        if count < 0:
            raise WebTabError("count needs to be positive!")

    def current_idx(self) -> int:
        raise NotImplementedError

    def back(self, count: int = 1) -> None:
        """Go back in the tab's history."""
        self._check_count(count)
        idx = self.current_idx() - count
        if idx >= 0:
            self._go_to_item(self._item_at(idx))
        else:
            self._go_to_item(self._item_at(0))
            raise WebTabError("At beginning of history.")

    def forward(self, count: int = 1) -> None:
        """Go forward in the tab's history."""
        self._check_count(count)
        idx = self.current_idx() + count
        if idx < len(self):
            self._go_to_item(self._item_at(idx))
        else:
            self._go_to_item(self._item_at(len(self) - 1))
            raise WebTabError("At end of history.")

    def can_go_back(self) -> bool:
        raise NotImplementedError

    def can_go_forward(self) -> bool:
        raise NotImplementedError

    def _item_at(self, i: int) -> typing.Any:
        raise NotImplementedError

    def _go_to_item(self, item: typing.Any) -> None:
        raise NotImplementedError


class AbstractElements:

    """Finding and handling of elements on the page."""

    _MultiCallback = typing.Callable[
        [typing.Sequence['webelem.AbstractWebElement']], None]
    _SingleCallback = typing.Callable[
        [typing.Optional['webelem.AbstractWebElement']], None]
    _ErrorCallback = typing.Callable[[Exception], None]

    def __init__(self) -> None:
        self._widget = typing.cast(QWidget, None)
        # self._tab is set by subclasses so mypy knows its concrete type.

    def find_css(self, selector: str,
                 callback: _MultiCallback,
                 error_cb: _ErrorCallback, *,
                 only_visible: bool = False) -> None:
        """Find all HTML elements matching a given selector async.

        If there's an error, the callback is called with a webelem.Error
        instance.

        Args:
            callback: The callback to be called when the search finished.
            error_cb: The callback to be called when an error occurred.
            selector: The CSS selector to search for.
            only_visible: Only show elements which are visible on screen.
        """
        raise NotImplementedError

    def find_id(self, elem_id: str, callback: _SingleCallback) -> None:
        """Find the HTML element with the given ID async.

        Args:
            callback: The callback to be called when the search finished.
                      Called with a WebEngineElement or None.
            elem_id: The ID to search for.
        """
        raise NotImplementedError

    def find_focused(self, callback: _SingleCallback) -> None:
        """Find the focused element on the page async.

        Args:
            callback: The callback to be called when the search finished.
                      Called with a WebEngineElement or None.
        """
        raise NotImplementedError

    def find_at_pos(self, pos: QPoint, callback: _SingleCallback) -> None:
        """Find the element at the given position async.

        This is also called "hit test" elsewhere.

        Args:
            pos: The QPoint to get the element for.
            callback: The callback to be called when the search finished.
                      Called with a WebEngineElement or None.
        """
        raise NotImplementedError


class AbstractAudio(QObject):

    """Handling of audio/muting for this tab."""

    muted_changed = pyqtSignal(bool)
    recently_audible_changed = pyqtSignal(bool)

    def __init__(self, tab: 'AbstractTab', parent: QWidget = None) -> None:
        super().__init__(parent)
        self._widget = typing.cast(QWidget, None)
        self._tab = tab

    def set_muted(self, muted: bool, override: bool = False) -> None:
        """Set this tab as muted or not.

        Arguments:
            override: If set to True, muting/unmuting was done manually and
                      overrides future automatic mute/unmute changes based on
                      the URL.
        """
        raise NotImplementedError

    def is_muted(self) -> bool:
        raise NotImplementedError

    def is_recently_audible(self) -> bool:
        """Whether this tab has had audio playing recently."""
        raise NotImplementedError


class AbstractTabPrivate:

    """Tab-related methods which are only needed in the core.

    Those methods are not part of the API which is exposed to extensions, and
    should ideally be removed at some point in the future.
    """

    def __init__(self, mode_manager: modeman.ModeManager,
                 tab: 'AbstractTab') -> None:
        self._widget = typing.cast(QWidget, None)
        self._tab = tab
        self._mode_manager = mode_manager

    def event_target(self) -> QWidget:
        """Return the widget events should be sent to."""
        raise NotImplementedError

    def handle_auto_insert_mode(self, ok: bool) -> None:
        """Handle `input.insert_mode.auto_load` after loading finished."""
        if not ok or not config.cache['input.insert_mode.auto_load']:
            return

        cur_mode = self._mode_manager.mode
        if cur_mode == usertypes.KeyMode.insert:
            return

        def _auto_insert_mode_cb(
                elem: typing.Optional['webelem.AbstractWebElement']
        ) -> None:
            """Called from JS after finding the focused element."""
            if elem is None:
                log.webview.debug("No focused element!")
                return
            if elem.is_editable():
                modeman.enter(self._tab.win_id, usertypes.KeyMode.insert,
                              'load finished', only_if_normal=True)

        self._tab.elements.find_focused(_auto_insert_mode_cb)

    def clear_ssl_errors(self) -> None:
        raise NotImplementedError

    def networkaccessmanager(self) -> typing.Optional[QNetworkAccessManager]:
        """Get the QNetworkAccessManager for this tab.

        This is only implemented for QtWebKit.
        For QtWebEngine, always returns None.
        """
        raise NotImplementedError

    def shutdown(self) -> None:
        raise NotImplementedError

    def run_js_sync(self, code: str) -> None:
        """Run javascript sync.

        Result will be returned when running JS is complete.
        This is only implemented for QtWebKit.
        For QtWebEngine, always raises UnsupportedOperationError.
        """
        raise NotImplementedError


class AbstractTab(QWidget):

    """An adapter for QWebView/QWebEngineView representing a single tab."""

    #: Signal emitted when a website requests to close this tab.
    window_close_requested = pyqtSignal()
    #: Signal emitted when a link is hovered (the hover text)
    link_hovered = pyqtSignal(str)
    #: Signal emitted when a page started loading
    load_started = pyqtSignal()
    #: Signal emitted when a page is loading (progress percentage)
    load_progress = pyqtSignal(int)
    #: Signal emitted when a page finished loading (success as bool)
    load_finished = pyqtSignal(bool)
    #: Signal emitted when a page's favicon changed (icon as QIcon)
    icon_changed = pyqtSignal(QIcon)
    #: Signal emitted when a page's title changed (new title as str)
    title_changed = pyqtSignal(str)
    #: Signal emitted when a new tab should be opened (url as QUrl)
    new_tab_requested = pyqtSignal(QUrl)
    #: Signal emitted when a page's URL changed (url as QUrl)
    url_changed = pyqtSignal(QUrl)
    #: Signal emitted when a tab's content size changed
    #: (new size as QSizeF)
    contents_size_changed = pyqtSignal(QSizeF)
    #: Signal emitted when a page requested full-screen (bool)
    fullscreen_requested = pyqtSignal(bool)
    #: Signal emitted before load starts (URL as QUrl)
    before_load_started = pyqtSignal(QUrl)

    # Signal emitted when a page's load status changed
    # (argument: usertypes.LoadStatus)
    load_status_changed = pyqtSignal(usertypes.LoadStatus)
    # Signal emitted before shutting down
    shutting_down = pyqtSignal()
    # Signal emitted when a history item should be added
    history_item_triggered = pyqtSignal(QUrl, QUrl, str)
    # Signal emitted when the underlying renderer process terminated.
    # arg 0: A TerminationStatus member.
    # arg 1: The exit code.
    renderer_process_terminated = pyqtSignal(TerminationStatus, int)

    # Hosts for which a certificate error happened. Shared between all tabs.
    #
    # Note that we remember hosts here, without scheme/port:
    # QtWebEngine/Chromium also only remembers hostnames, and certificates are
    # for a given hostname anyways.
    _insecure_hosts = set()  # type: typing.Set[str]

    def __init__(self, *, win_id: int,
                 mode_manager: modeman.ModeManager,
                 private: bool,
                 parent: QWidget = None) -> None:
        utils.unused(mode_manager)  # needed for mypy
        self.is_private = private
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
        self._widget = typing.cast(QWidget, None)
        self._progress = 0
        self._load_status = usertypes.LoadStatus.none
        self._tab_event_filter = eventfilter.TabEventFilter(
            self, parent=self)
        self.backend = None  # type: typing.Optional[usertypes.Backend]

        # If true, this tab has been requested to be removed (or is removed).
        self.pending_removal = False
        self.shutting_down.connect(functools.partial(
            setattr, self, 'pending_removal', True))

        self.before_load_started.connect(self._on_before_load_started)

    def _set_widget(self, widget: QWidget) -> None:
        # pylint: disable=protected-access
        self._widget = widget
        self._layout.wrap(self, widget)
        self.history._history = widget.history()
        self.history.private_api._history = widget.history()
        self.scroller._init_widget(widget)
        self.caret._widget = widget
        self.zoom._widget = widget
        self.search._widget = widget
        self.printing._widget = widget
        self.action._widget = widget
        self.elements._widget = widget
        self.audio._widget = widget
        self.private_api._widget = widget
        self.settings._settings = widget.settings()

        self._install_event_filter()
        self.zoom.apply_default()

    def _install_event_filter(self) -> None:
        raise NotImplementedError

    def _set_load_status(self, val: usertypes.LoadStatus) -> None:
        """Setter for load_status."""
        if not isinstance(val, usertypes.LoadStatus):
            raise TypeError("Type {} is no LoadStatus member!".format(val))
        log.webview.debug("load status for {}: {}".format(repr(self), val))
        self._load_status = val
        self.load_status_changed.emit(val)

    def send_event(self, evt: QEvent) -> None:
        """Send the given event to the underlying widget.

        The event will be sent via QApplication.postEvent.
        Note that a posted event must not be re-used in any way!
        """
        # This only gives us some mild protection against re-using events, but
        # it's certainly better than a segfault.
        if getattr(evt, 'posted', False):
            raise utils.Unreachable("Can't re-use an event which was already "
                                    "posted!")

        recipient = self.private_api.event_target()
        if recipient is None:
            # https://github.com/qutebrowser/qutebrowser/issues/3888
            log.webview.warning("Unable to find event target!")
            return

        evt.posted = True  # type: ignore[attr-defined]
        QApplication.postEvent(recipient, evt)

    def navigation_blocked(self) -> bool:
        """Test if navigation is allowed on the current tab."""
        return self.data.pinned and config.val.tabs.pinned.frozen

    @pyqtSlot(QUrl)
    def _on_before_load_started(self, url: QUrl) -> None:
        """Adjust the title if we are going to visit a URL soon."""
        qtutils.ensure_valid(url)
        url_string = url.toDisplayString()
        log.webview.debug("Going to start loading: {}".format(url_string))
        self.title_changed.emit(url_string)

    @pyqtSlot(QUrl)
    def _on_url_changed(self, url: QUrl) -> None:
        """Update title when URL has changed and no title is available."""
        if url.isValid() and not self.title():
            self.title_changed.emit(url.toDisplayString())
        self.url_changed.emit(url)

    @pyqtSlot()
    def _on_load_started(self) -> None:
        self._progress = 0
        self.data.viewing_source = False
        self._set_load_status(usertypes.LoadStatus.loading)
        self.load_started.emit()

    @pyqtSlot(usertypes.NavigationRequest)
    def _on_navigation_request(
            self,
            navigation: usertypes.NavigationRequest
    ) -> None:
        """Handle common acceptNavigationRequest code."""
        url = utils.elide(navigation.url.toDisplayString(), 100)
        log.webview.debug("navigation request: url {}, type {}, is_main_frame "
                          "{}".format(url,
                                      navigation.navigation_type,
                                      navigation.is_main_frame))

        if navigation.is_main_frame:
            self.data.last_navigation = navigation

        if not navigation.url.isValid():
            # Also a WORKAROUND for missing IDNA 2008 support in QUrl, see
            # https://bugreports.qt.io/browse/QTBUG-60364

            if navigation.navigation_type == navigation.Type.link_clicked:
                msg = urlutils.get_errstring(navigation.url,
                                             "Invalid link clicked")
                message.error(msg)
                self.data.open_target = usertypes.ClickTarget.normal

            log.webview.debug("Ignoring invalid URL {} in "
                              "acceptNavigationRequest: {}".format(
                                  navigation.url.toDisplayString(),
                                  navigation.url.errorString()))
            navigation.accepted = False

    @pyqtSlot(bool)
    def _on_load_finished(self, ok: bool) -> None:
        assert self._widget is not None
        if sip.isdeleted(self._widget):
            # https://github.com/qutebrowser/qutebrowser/issues/3498
            return

        if sessions.session_manager is not None:
            sessions.session_manager.save_autosave()

        self.load_finished.emit(ok)

        if not self.title():
            self.title_changed.emit(self.url().toDisplayString())

        self.zoom.reapply()

    def _update_load_status(self, ok: bool) -> None:
        """Update the load status after a page finished loading.

        Needs to be called by subclasses to trigger a load status update, e.g.
        as a response to a loadFinished signal.
        """
        url = self.url()
        is_https = url.scheme() == 'https'

        if not ok:
            loadstatus = usertypes.LoadStatus.error
        elif is_https and url.host() in self._insecure_hosts:
            loadstatus = usertypes.LoadStatus.warn
        elif is_https:
            loadstatus = usertypes.LoadStatus.success_https
        else:
            loadstatus = usertypes.LoadStatus.success

        self._set_load_status(loadstatus)

    @pyqtSlot()
    def _on_history_trigger(self) -> None:
        """Emit history_item_triggered based on backend-specific signal."""
        raise NotImplementedError

    @pyqtSlot(int)
    def _on_load_progress(self, perc: int) -> None:
        self._progress = perc
        self.load_progress.emit(perc)

    def url(self, *, requested: bool = False) -> QUrl:
        raise NotImplementedError

    def progress(self) -> int:
        return self._progress

    def load_status(self) -> usertypes.LoadStatus:
        return self._load_status

    def _load_url_prepare(self, url: QUrl, *,
                          emit_before_load_started: bool = True) -> None:
        qtutils.ensure_valid(url)
        if emit_before_load_started:
            self.before_load_started.emit(url)

    def load_url(self, url: QUrl, *,
                 emit_before_load_started: bool = True) -> None:
        raise NotImplementedError

    def reload(self, *, force: bool = False) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def fake_key_press(self,
                       key: Qt.Key,
                       modifier: Qt.KeyboardModifier = Qt.NoModifier) -> None:
        """Send a fake key event to this tab."""
        press_evt = QKeyEvent(QEvent.KeyPress, key, modifier, 0, 0, 0)
        release_evt = QKeyEvent(QEvent.KeyRelease, key, modifier,
                                0, 0, 0)
        self.send_event(press_evt)
        self.send_event(release_evt)

    def dump_async(self,
                   callback: typing.Callable[[str], None], *,
                   plain: bool = False) -> None:
        """Dump the current page's html asynchronously.

        The given callback will be called with the result when dumping is
        complete.
        """
        raise NotImplementedError

    def run_js_async(
            self,
            code: str,
            callback: typing.Callable[[typing.Any], None] = None, *,
            world: typing.Union[usertypes.JsWorld, int] = None
    ) -> None:
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

    def title(self) -> str:
        raise NotImplementedError

    def icon(self) -> None:
        raise NotImplementedError

    def set_html(self, html: str, base_url: QUrl = QUrl()) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        try:
            qurl = self.url()
            url = qurl.toDisplayString(
                QUrl.EncodeUnicode)  # type: ignore[arg-type]
        except (AttributeError, RuntimeError) as exc:
            url = '<{}>'.format(exc.__class__.__name__)
        else:
            url = utils.elide(url, 100)
        return utils.get_repr(self, tab_id=self.tab_id, url=url)

    def is_deleted(self) -> bool:
        assert self._widget is not None
        return sip.isdeleted(self._widget)
