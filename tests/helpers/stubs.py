# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=invalid-name,abstract-method

"""Fake objects/stubs."""

from unittest import mock

import attr
from PyQt5.QtCore import pyqtSignal, QPoint, QProcess, QObject, QUrl
from PyQt5.QtNetwork import (QNetworkRequest, QAbstractNetworkCache,
                             QNetworkCacheMetaData)
from PyQt5.QtWidgets import QCommonStyle, QLineEdit, QWidget, QTabBar

from qutebrowser.browser import browsertab
from qutebrowser.utils import usertypes
from qutebrowser.mainwindow import mainwindow


class FakeNetworkCache(QAbstractNetworkCache):

    """Fake cache with no data."""

    def cacheSize(self):
        return 0

    def data(self, _url):
        return None

    def insert(self, _dev):
        pass

    def metaData(self, _url):
        return QNetworkCacheMetaData()

    def prepare(self, _metadata):
        return None

    def remove(self, _url):
        return False

    def updateMetaData(self, _url):
        pass


class FakeKeyEvent:

    """Fake QKeyPressEvent stub."""

    def __init__(self, key, modifiers=0, text=''):
        self.key = mock.Mock(return_value=key)
        self.text = mock.Mock(return_value=text)
        self.modifiers = mock.Mock(return_value=modifiers)


class FakeWebFrame:

    """A stub for QWebFrame."""

    def __init__(self, geometry=None, *, scroll=None, plaintext=None,
                 html=None, parent=None, zoom=1.0):
        """Constructor.

        Args:
            geometry: The geometry of the frame as QRect.
            scroll: The scroll position as QPoint.
            plaintext: Return value of toPlainText
            html: Return value of tohtml.
            zoom: The zoom factor.
            parent: The parent frame.
        """
        if scroll is None:
            scroll = QPoint(0, 0)
        self.geometry = mock.Mock(return_value=geometry)
        self.scrollPosition = mock.Mock(return_value=scroll)
        self.parentFrame = mock.Mock(return_value=parent)
        self.toPlainText = mock.Mock(return_value=plaintext)
        self.toHtml = mock.Mock(return_value=html)
        self.zoomFactor = mock.Mock(return_value=zoom)


class FakeChildrenFrame:

    """A stub for QWebFrame to test get_child_frames."""

    def __init__(self, children=None):
        if children is None:
            children = []
        self.childFrames = mock.Mock(return_value=children)


class FakeQApplication:

    """Stub to insert as QApplication module."""

    UNSET = object()

    def __init__(self, style=None, all_widgets=None, active_window=None,
                 instance=UNSET):

        if instance is self.UNSET:
            self.instance = mock.Mock(return_value=self)
        else:
            self.instance = mock.Mock(return_value=instance)

        self.style = mock.Mock(spec=QCommonStyle)
        self.style().metaObject().className.return_value = style

        self.allWidgets = lambda: all_widgets
        self.activeWindow = lambda: active_window


class FakeNetworkReply:

    """QNetworkReply stub which provides a Content-Disposition header."""

    KNOWN_HEADERS = {
        QNetworkRequest.ContentTypeHeader: 'Content-Type',
    }

    def __init__(self, headers=None, url=None):
        if url is None:
            url = QUrl()
        if headers is None:
            self.headers = {}
        else:
            self.headers = headers
        self.url = mock.Mock(return_value=url)

    def hasRawHeader(self, name):
        """Check if the reply has a certain header.

        Args:
            name: The name of the header as ISO-8859-1 encoded bytes object.

        Return:
            True if the header is present, False if not.
        """
        return name.decode('iso-8859-1') in self.headers

    def rawHeader(self, name):
        """Get the raw header data of a header.

        Args:
            name: The name of the header as ISO-8859-1 encoded bytes object.

        Return:
            The header data, as ISO-8859-1 encoded bytes() object.
        """
        name = name.decode('iso-8859-1')
        return self.headers[name].encode('iso-8859-1')

    def header(self, known_header):
        """Get a known header.

        Args:
            known_header: A QNetworkRequest::KnownHeaders member.
        """
        key = self.KNOWN_HEADERS[known_header]
        try:
            return self.headers[key]
        except KeyError:
            return None

    def setHeader(self, known_header, value):
        """Set a known header.

        Args:
            known_header: A QNetworkRequest::KnownHeaders member.
            value: The value to set.
        """
        key = self.KNOWN_HEADERS[known_header]
        self.headers[key] = value


def fake_qprocess():
    """Factory for a QProcess mock which has the QProcess enum values."""
    m = mock.Mock(spec=QProcess)
    for name in ['NormalExit', 'CrashExit', 'FailedToStart', 'Crashed',
                 'Timedout', 'WriteError', 'ReadError', 'UnknownError']:
        setattr(m, name, getattr(QProcess, name))
    return m


class FakeWebTabScroller(browsertab.AbstractScroller):

    """Fake AbstractScroller to use in tests."""

    def __init__(self, tab, pos_perc):
        super().__init__(tab)
        self._pos_perc = pos_perc

    def pos_perc(self):
        return self._pos_perc


class FakeWebTabHistory(browsertab.AbstractHistory):

    """Fake for Web{Kit,Engine}History."""

    def __init__(self, tab, *, can_go_back, can_go_forward):
        super().__init__(tab)
        self._can_go_back = can_go_back
        self._can_go_forward = can_go_forward

    def can_go_back(self):
        assert self._can_go_back is not None
        return self._can_go_back

    def can_go_forward(self):
        assert self._can_go_forward is not None
        return self._can_go_forward


class FakeWebTab(browsertab.AbstractTab):

    """Fake AbstractTab to use in tests."""

    def __init__(self, url=QUrl(), title='', tab_id=0, *,
                 scroll_pos_perc=(0, 0),
                 load_status=usertypes.LoadStatus.success,
                 progress=0, can_go_back=None, can_go_forward=None):
        super().__init__(win_id=0, mode_manager=None, private=False)
        self._load_status = load_status
        self._title = title
        self._url = url
        self._progress = progress
        self.history = FakeWebTabHistory(self, can_go_back=can_go_back,
                                         can_go_forward=can_go_forward)
        self.scroller = FakeWebTabScroller(self, scroll_pos_perc)
        wrapped = QWidget()
        self._layout.wrap(self, wrapped)

    def url(self, requested=False):
        assert not requested
        return self._url

    def title(self):
        return self._title

    def progress(self):
        return self._progress

    def load_status(self):
        return self._load_status


class FakeSignal:

    """Fake pyqtSignal stub which does nothing.

    Attributes:
        signal: The name of the signal, like pyqtSignal.
        _func: The function to be invoked when the signal gets called.
    """

    def __init__(self, name='fake', func=None):
        self.signal = '2{}(int, int)'.format(name)
        self._func = func

    def __call__(self):
        if self._func is None:
            raise TypeError("'FakeSignal' object is not callable")
        else:
            return self._func()

    def connect(self, slot):
        """Connect the signal to a slot.

        Currently does nothing, but could be improved to do some sanity
        checking on the slot.
        """
        pass

    def disconnect(self, slot=None):
        """Disconnect the signal from a slot.

        Currently does nothing, but could be improved to do some sanity
        checking on the slot and see if it actually got connected.
        """
        pass

    def emit(self, *args):
        """Emit the signal.

        Currently does nothing, but could be improved to do type checking based
        on a signature given to __init__.
        """
        pass


@attr.s
class FakeCmdUtils:

    """Stub for cmdutils which provides a cmd_dict."""

    cmd_dict = attr.ib()


@attr.s(frozen=True)
class FakeCommand:

    """A simple command stub which has a description."""

    name = attr.ib('')
    desc = attr.ib('')
    hide = attr.ib(False)
    debug = attr.ib(False)
    deprecated = attr.ib(False)
    completion = attr.ib(None)
    maxsplit = attr.ib(None)
    takes_count = attr.ib(lambda: False)
    modes = attr.ib((usertypes.KeyMode.normal, ))


class FakeTimer(QObject):

    """Stub for a usertypes.Timer."""

    timeout_signal = pyqtSignal()

    def __init__(self, parent=None, name=None):
        super().__init__(parent)
        self.timeout = mock.Mock(spec=['connect', 'disconnect', 'emit'])
        self.timeout.connect.side_effect = self.timeout_signal.connect
        self.timeout.disconnect.side_effect = self.timeout_signal.disconnect
        self.timeout.emit.side_effect = self._emit
        self._started = False
        self._singleshot = False
        self._interval = 0
        self._name = name

    def __repr__(self):
        return '<{} name={!r}>'.format(self.__class__.__name__, self._name)

    def _emit(self):
        """Called when the timeout "signal" gets emitted."""
        if self._singleshot:
            self._started = False
        self.timeout_signal.emit()

    def setInterval(self, interval):
        self._interval = interval

    def interval(self):
        return self._interval

    def setSingleShot(self, singleshot):
        self._singleshot = singleshot

    def isSingleShot(self):
        return self._singleshot

    def start(self, interval=None):
        if interval:
            self._interval = interval
        self._started = True

    def stop(self):
        self._started = False

    def isActive(self):
        return self._started


class InstaTimer(QObject):

    """Stub for a QTimer that fires instantly on start().

    Useful to test a time-based event without inserting an artificial delay.
    """

    timeout = pyqtSignal()

    def start(self, interval=None):
        self.timeout.emit()

    def setSingleShot(self, yes):
        pass

    def setInterval(self, interval):
        pass

    @staticmethod
    def singleShot(_interval, fun):
        fun()


class FakeYamlConfig:

    """Fake configfiles.YamlConfig object."""

    def __init__(self):
        self.loaded = False
        self._values = {}

    def __contains__(self, item):
        return item in self._values

    def __iter__(self):
        return iter(self._values.items())

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]

    def unset(self, name):
        self._values.pop(name, None)

    def clear(self):
        self._values = []


class StatusBarCommandStub(QLineEdit):

    """Stub for the statusbar command prompt."""

    got_cmd = pyqtSignal(str)
    clear_completion_selection = pyqtSignal()
    hide_completion = pyqtSignal()
    update_completion = pyqtSignal()
    show_cmd = pyqtSignal()
    hide_cmd = pyqtSignal()

    def prefix(self):
        return self.text()[0]


class UrlMarkManagerStub(QObject):

    """Stub for the quickmark-manager or bookmark-manager object."""

    added = pyqtSignal(str, str)
    removed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.marks = {}

    def delete(self, key):
        del self.marks[key]
        self.removed.emit(key)


class BookmarkManagerStub(UrlMarkManagerStub):

    """Stub for the bookmark-manager object."""

    pass


class QuickmarkManagerStub(UrlMarkManagerStub):

    """Stub for the quickmark-manager object."""

    def quickmark_del(self, key):
        self.delete(key)


class HostBlockerStub:

    """Stub for the host-blocker object."""

    def __init__(self):
        self.blocked_hosts = set()


class SessionManagerStub:

    """Stub for the session-manager object."""

    def __init__(self):
        self.sessions = []

    def list_sessions(self):
        return self.sessions


class TabbedBrowserStub(QObject):

    """Stub for the tabbed-browser object."""

    new_tab = pyqtSignal(browsertab.AbstractTab, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = []
        self.shutting_down = False
        self._qtabbar = QTabBar()
        self.index_of = None
        self.current_index = None
        self.opened_url = None

    def count(self):
        return len(self.tabs)

    def widgets(self):
        return self.tabs

    def widget(self, i):
        return self.tabs[i]

    def page_title(self, i):
        return self.tabs[i].title()

    def on_tab_close_requested(self, idx):
        del self.tabs[idx]

    def tabBar(self):
        return self._qtabbar

    def indexOf(self, _tab):
        if self.index_of is None:
            raise ValueError("indexOf got called with index_of None!")
        elif self.index_of is RuntimeError:
            raise RuntimeError
        else:
            return self.index_of

    def currentIndex(self):
        if self.current_index is None:
            raise ValueError("currentIndex got called with current_index "
                             "None!")
        return self.current_index

    def currentWidget(self):
        idx = self.currentIndex()
        if idx == -1:
            return None
        return self.tabs[idx - 1]

    def tabopen(self, url):
        self.opened_url = url

    def openurl(self, url, *, newtab):
        self.opened_url = url


class ApplicationStub(QObject):

    """Stub to insert as the app object in objreg."""

    new_window = pyqtSignal(mainwindow.MainWindow)
