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

"""Base class for a wrapper over QWebView/QWebEngineView."""

import itertools

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QUrl, QObject, QPoint
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QLayout

from qutebrowser.config import config
from qutebrowser.utils import utils, objreg, usertypes


tab_id_gen = itertools.count(0)


class WebTabError(Exception):

    """Base class for various errors."""


class WrapperLayout(QLayout):

    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget

    def addItem(self, w):
        raise AssertionError("Should never be called!")

    def sizeHint(self):
        return self._widget.sizeHint()

    def itemAt(self, i):
        # FIXME why does this get called?
        return None

    def takeAt(self, i):
        raise AssertionError("Should never be called!")

    def setGeometry(self, r):
        self._widget.setGeometry(r)


class AbstractSearch(QObject):

    """Attribute of AbstractTab for doing searches.

    Attributes:
        widget: The underlying WebView widget.
        text: The last thing this view was searched for.
        _flags: The flags of the last search.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget = None
        self.text = None
        self._flags = 0

    def search(self, text, *, ignore_case=False, wrap=False):
        """Find the given text on the page.

        Args:
            text: The text to search for.
            ignore_case: Search case-insensitively. (True/False/'smart')
            wrap: Wrap around to the top when arriving at the bottom.
            reverse: Reverse search direction.
        """
        raise NotImplementedError

    def clear(self):
        """Clear the current search."""
        raise NotImplementedError

    def prev_result(self):
        """Go to the previous result of the current search."""
        raise NotImplementedError

    def next_result(self):
        """Go to the next result of the current search."""
        raise NotImplementedError


class AbstractZoom(QObject):

    """Attribute of AbstractTab for controlling zoom.

    Attributes:
        _neighborlist: A NeighborList with the zoom levels.
        _default_zoom_changed: Whether the zoom was changed from the default.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._widget = None
        self._win_id = win_id
        self._default_zoom_changed = False
        self._init_neighborlist()
        objreg.get('config').changed.connect(self.on_config_changed)

        # # FIXME is this needed?
        # # For some reason, this signal doesn't get disconnected automatically
        # # when the WebView is destroyed on older PyQt versions.
        # # See https://github.com/The-Compiler/qutebrowser/issues/390
        # self.destroyed.connect(functools.partial(
        #     cfg.changed.disconnect, self.init_neighborlist))

    def _set_default_zoom(self):
        default_zoom = config.get('ui', 'default-zoom')
        self._set_factor_internal(float(default_zoom) / 100)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        if section == 'ui' and option in ('zoom-levels', 'default-zoom'):
            if not self._default_zoom_changed:
                factor = float(config.get('ui', 'default-zoom')) / 100
                self._set_factor_internal(factor)
            self._default_zoom_changed = False
            self._init_neighborlist()

    def _init_neighborlist(self):
        """Initialize self._neighborlist."""
        levels = config.get('ui', 'zoom-levels')
        self._neighborlist = usertypes.NeighborList(
            levels, mode=usertypes.NeighborList.Modes.edge)
        self._neighborlist.fuzzyval = config.get('ui', 'default-zoom')

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
        self._default_zoom_changed = True
        self._set_factor_internal(factor)

    def factor(self):
        raise NotImplementedError

    @pyqtSlot(QPoint)
    def on_mouse_wheel_zoom(self, delta):
        """Handle zooming via mousewheel requested by the web view."""
        divider = config.get('input', 'mouse-zoom-divider')
        factor = self.zoomFactor() + delta.y() / divider
        if factor < 0:
            return
        perc = int(100 * factor)
        message.info(self.win_id, "Zoom level: {}%".format(perc))
        self._neighborlist.fuzzyval = perc
        self._set_factor_internal(factor)
        self._default_zoom_changed = True


class AbstractCaret(QObject):

    """Attribute of AbstractTab for caret browsing."""

    def __init__(self, win_id, tab, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._win_id = win_id
        self._widget = None
        self.selection_enabled = False
        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=win_id)
        mode_manager.entered.connect(self.on_mode_entered)
        mode_manager.left.connect(self.on_mode_left)

    def on_mode_entered(self):
        raise NotImplementedError

    def on_mode_left(self):
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

    def has_selection(self):
        raise NotImplementedError

    def selection(self, html=False):
        raise NotImplementedError

    def follow_selected(self, tab=False):
        raise NotImplementedError


class AbstractScroller(QObject):

    """Attribute of AbstractTab to manage scroll position."""

    perc_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget = None

    def pos_px(self):
        raise NotImplementedError

    def pos_perc(self):
        raise NotImplementedError

    def to_perc(self, x=None, y=None):
        raise NotImplementedError

    def to_point(self, point):
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

    def back(self):
        raise NotImplementedError

    def forward(self):
        raise NotImplementedError

    def can_go_back(self):
        raise NotImplementedError

    def can_go_forward(self):
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


class AbstractTab(QWidget):

    """A wrapper over the given widget to hide its API and expose another one.

    We use this to unify QWebView and QWebEngineView.

    Attributes:
        keep_icon: Whether the (e.g. cloned) icon should not be cleared on page
                   load.
        history: The AbstractHistory for the current tab.

        for properties, see WebView/WebEngineView docs.

    Signals:
        See related Qt signals.

        new_tab_requested: Emitted when a new tab should be opened with the
                           given URL.
    """

    window_close_requested = pyqtSignal()
    link_hovered = pyqtSignal(str)
    load_started = pyqtSignal()
    load_progress = pyqtSignal(int)
    load_finished = pyqtSignal(bool)
    icon_changed = pyqtSignal(QIcon)
    # FIXME:refactor get rid of this altogether?
    url_text_changed = pyqtSignal(str)
    title_changed = pyqtSignal(str)
    load_status_changed = pyqtSignal(str)
    new_tab_requested = pyqtSignal(QUrl)
    shutting_down = pyqtSignal()

    def __init__(self, win_id, parent=None):
        self.win_id = win_id
        self.tab_id = next(tab_id_gen)
        super().__init__(parent)
        # self.history = AbstractHistory(self)
        # self.scroll = AbstractScroller(parent=self)
        # self.caret = AbstractCaret(win_id=win_id, tab=self, parent=self)
        # self.zoom = AbstractZoom(win_id=win_id)
        # self.search = AbstractSearch(parent=self)
        self._layout = None
        self._widget = None
        self.keep_icon = False  # FIXME:refactor get rid of this?

    def _set_widget(self, widget):
        self._layout = WrapperLayout(widget, self)
        self._widget = widget
        self.history._history = widget.history()
        self.scroll._widget = widget
        self.caret._widget = widget
        self.zoom._widget = widget
        self.search._widget = widget
        widget.mouse_wheel_zoom.connect(self.zoom.on_mouse_wheel_zoom)
        widget.setParent(self)

    @property
    def cur_url(self):
        raise NotImplementedError

    @property
    def progress(self):
        raise NotImplementedError

    @property
    def load_status(self):
        raise NotImplementedError

    def openurl(self, url):
        raise NotImplementedError

    def reload(self, *, force=False):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def dump_async(self, callback, *, plain=False):
        """Dump the current page to a file ascync.

        The given callback will be called with the result when dumping is
        complete.
        """
        raise NotImplementedError

    def run_js_async(self, code, callback=None):
        """Run javascript async.

        The given callback will be called with the result when running JS is
        complete.
        """
        raise NotImplementedError

    def shutdown(self):
        raise NotImplementedError

    def title(self):
        raise NotImplementedError

    def icon(self):
        raise NotImplementedError

    def __repr__(self):
        url = utils.elide(self.cur_url.toDisplayString(QUrl.EncodeUnicode),
                          100)
        return utils.get_repr(self, tab_id=self.tab_id, url=url)
