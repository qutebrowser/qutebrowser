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

from PyQt5.QtCore import pyqtSignal, QUrl
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QLayout

from qutebrowser.utils import utils


tab_id_gen = itertools.count(0)



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


class AbstractHistory:

    """The history attribute of a AbstractTab."""

    def __init__(self, tab):
        self.tab = tab
        self.widget = None

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
    """

    window_close_requested = pyqtSignal()
    link_hovered = pyqtSignal(str)
    load_started = pyqtSignal()
    load_progress = pyqtSignal(int)
    load_finished = pyqtSignal(bool)
    scroll_pos_changed = pyqtSignal(int, int)
    icon_changed = pyqtSignal(QIcon)
    # FIXME:refactor get rid of this altogether?
    url_text_changed = pyqtSignal(str)
    title_changed = pyqtSignal(str)
    load_status_changed = pyqtSignal(str)
    shutting_down = pyqtSignal()

    def __init__(self, parent=None):
        self.tab_id = next(tab_id_gen)
        super().__init__(parent)
        self.history = AbstractHistory(self)
        self._layout = None
        self._widget = None
        self.keep_icon = False  # FIXME:refactor get rid of this?

    def _set_widget(self, widget):
        self._layout = WrapperLayout(widget, self)
        self._widget = widget
        self.history.history = widget.history()
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

    @property
    def scroll_pos(self):
        raise NotImplementedError

    def openurl(self, url):
        raise NotImplementedError

    def reload(self, *, force=False):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def dump_async(self, callback=None, *, plain=False):
        """Dump the current page to a file ascync.

        The given callback will be called with the result when dumping is
        complete.
        """
        raise NotImplementedError

    def shutdown(self):
        raise NotImplementedError

    def __repr__(self):
        url = utils.elide(self.cur_url.toDisplayString(QUrl.EncodeUnicode),
                          100)
        return utils.get_repr(self, tab_id=self.tab_id, url=url)
