# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

# pylint: disable=abstract-method

"""Fake objects/stubs."""

from typing import Any, Callable, Tuple
from unittest import mock
import contextlib
import shutil
import dataclasses
import builtins
import importlib
import types

from PyQt5.QtCore import pyqtSignal, QPoint, QProcess, QObject, QUrl, QByteArray
from PyQt5.QtGui import QIcon
from PyQt5.QtNetwork import (QNetworkRequest, QAbstractNetworkCache,
                             QNetworkCacheMetaData)
from PyQt5.QtWidgets import QCommonStyle, QLineEdit, QWidget, QTabBar

from qutebrowser.browser import browsertab, downloads
from qutebrowser.utils import usertypes
from qutebrowser.commands import runners


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

    def __init__(self, *, style=None, all_widgets=None, active_window=None,
                 arguments=None, platform_name=None):
        self.style = mock.Mock(spec=QCommonStyle)
        self.style().metaObject().className.return_value = style

        self.allWidgets = lambda: all_widgets
        self.activeWindow = lambda: active_window
        self.arguments = lambda: arguments
        self.platformName = lambda: platform_name


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


class FakeProcess(QProcess):

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self.start = mock.Mock(spec=QProcess.start)
        self.startDetached = mock.Mock(spec=QProcess.startDetached)
        self.readAllStandardOutput = mock.Mock(
            spec=QProcess.readAllStandardOutput, return_value=QByteArray(b''))
        self.readAllStandardError = mock.Mock(
            spec=QProcess.readAllStandardError, return_value=QByteArray(b''))
        self.terminate = mock.Mock(spec=QProcess.terminate)
        self.kill = mock.Mock(spec=QProcess.kill)


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


class FakeWebTabAudio(browsertab.AbstractAudio):

    def is_muted(self):
        return False

    def is_recently_audible(self):
        return False


class FakeWebTabPrivate(browsertab.AbstractTabPrivate):

    def shutdown(self):
        pass


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
        self.audio = FakeWebTabAudio(self)
        self.private_api = FakeWebTabPrivate(tab=self, mode_manager=None)
        wrapped = QWidget()
        self._layout.wrap(self, wrapped)

    def url(self, *, requested=False):
        assert not requested
        return self._url

    def title(self):
        return self._title

    def progress(self):
        return self._progress

    def load_status(self):
        return self._load_status

    def icon(self):
        return QIcon()

    def renderer_process_pid(self):
        return None

    def load_url(self, url):
        self._url = url


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
        return self._func()

    def connect(self, slot):
        """Connect the signal to a slot.

        Currently does nothing, but could be improved to do some sanity
        checking on the slot.
        """

    def disconnect(self, slot=None):
        """Disconnect the signal from a slot.

        Currently does nothing, but could be improved to do some sanity
        checking on the slot and see if it actually got connected.
        """

    def emit(self, *args):
        """Emit the signal.

        Currently does nothing, but could be improved to do type checking based
        on a signature given to __init__.
        """


@dataclasses.dataclass(frozen=True)
class FakeCommand:

    """A simple command stub which has a description."""

    name: str = ''
    desc: str = ''
    hide: bool = False
    debug: bool = False
    deprecated: bool = False
    completion: Any = None
    maxsplit: int = None
    takes_count: Callable[[], bool] = lambda: False
    modes: Tuple[usertypes.KeyMode] = (usertypes.KeyMode.normal, )


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


class QuickmarkManagerStub(UrlMarkManagerStub):

    """Stub for the quickmark-manager object."""

    def quickmark_del(self, key):
        self.delete(key)


class SessionManagerStub:

    """Stub for the session-manager object."""

    def __init__(self):
        self.sessions = []

    def list_sessions(self):
        return self.sessions

    def save_autosave(self):
        pass


class TabbedBrowserStub(QObject):

    """Stub for the tabbed-browser object."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget = TabWidgetStub()
        self.is_shutting_down = False
        self.loaded_url = None
        self.cur_url = None
        self.undo_stack = None

    def on_tab_close_requested(self, idx):
        del self.widget.tabs[idx]

    def widgets(self):
        return self.widget.tabs

    def tabopen(self, url):
        self.loaded_url = url

    def load_url(self, url, *, newtab):
        self.loaded_url = url

    def current_url(self):
        if self.current_url is None:
            raise ValueError("current_url got called with cur_url None!")
        return self.cur_url


class TabWidgetStub(QObject):

    """Stub for the tab-widget object."""

    new_tab = pyqtSignal(browsertab.AbstractTab, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = []
        self._qtabbar = QTabBar()
        self.index_of = None
        self.current_index = None

    def count(self):
        return len(self.tabs)

    def widget(self, i):
        return self.tabs[i]

    def page_title(self, i):
        return self.tabs[i].title()

    def tabBar(self):
        return self._qtabbar

    def indexOf(self, _tab):
        if self.index_of is None:
            raise ValueError("indexOf got called with index_of None!")
        if self.index_of is RuntimeError:
            raise RuntimeError
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


class HTTPPostStub(QObject):

    """A stub class for HTTPClient.

    Attributes:
        url: the last url send by post()
        data: the last data send by post()
    """

    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.url = None
        self.data = None

    def post(self, url, data=None):
        self.url = url
        self.data = data


class FakeDownloadItem(QObject):

    """Mock browser.downloads.DownloadItem."""

    finished = pyqtSignal()

    def __init__(self, fileobj, name, parent=None):
        super().__init__(parent)
        self.fileobj = fileobj
        self.name = name
        self.successful = False


class FakeDownloadManager:

    """Mock browser.downloads.DownloadManager."""

    def __init__(self, tmpdir):
        self._tmpdir = tmpdir
        self.downloads = []

    @contextlib.contextmanager
    def _open_fileobj(self, target):
        """Ensure a DownloadTarget's fileobj attribute is available."""
        if isinstance(target, downloads.FileDownloadTarget):
            target.fileobj = open(target.filename, 'wb')
            try:
                yield target.fileobj
            finally:
                target.fileobj.close()
        else:
            yield target.fileobj

    def get(self, url, target, **kwargs):
        """Return a FakeDownloadItem instance with a fileobj.

        The content is copied from the file the given url links to.
        """
        with self._open_fileobj(target):
            download_item = FakeDownloadItem(target.fileobj, name=url.path())
            with (self._tmpdir / url.path()).open('rb') as fake_url_file:
                shutil.copyfileobj(fake_url_file, download_item.fileobj)
        self.downloads.append(download_item)
        return download_item

    def has_downloads_with_nam(self, _nam):
        """Needed during WebView.shutdown()."""
        return False


class FakeHistoryProgress:

    """Fake for a WebHistoryProgress object."""

    def __init__(self, *, raise_on_tick=False):
        self._started = False
        self._finished = False
        self._value = 0
        self._raise_on_tick = raise_on_tick

    def start(self, _text):
        self._started = True

    def set_maximum(self, _maximum):
        pass

    def tick(self):
        if self._raise_on_tick:
            raise Exception('tick-tock')
        self._value += 1

    def finish(self):
        self._finished = True


class FakeCommandRunner(runners.AbstractCommandRunner):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.commands = []

    def run(self, text, count=None, *, safely=False):
        self.commands.append((text, count))


class FakeHintManager:

    def __init__(self):
        self.keystr = None

    def handle_partial_key(self, keystr):
        self.keystr = keystr

    def current_mode(self):
        return 'letter'


class FakeWebEngineProfile:

    def __init__(self, cookie_store):
        self.cookieStore = lambda: cookie_store


class FakeCookieStore:

    def __init__(self):
        self.cookie_filter = None

    def setCookieFilter(self, func):
        self.cookie_filter = func


class ImportFake:

    """A fake for __import__ which is used by the import_fake fixture.

    Attributes:
        modules: A dict mapping module names to bools. If True, the import will
                 succeed. Otherwise, it'll fail with ImportError.
        version_attribute: The name to use in the fake modules for the version
                           attribute.
        version: The version to use for the modules.
        _real_import: Saving the real __import__ builtin so the imports can be
                      done normally for modules not in self. modules.
    """

    def __init__(self, modules, monkeypatch):
        self._monkeypatch = monkeypatch
        self.modules = modules
        self.version_attribute = '__version__'
        self.version = '1.2.3'
        self._real_import = builtins.__import__
        self._real_importlib_import = importlib.import_module

    def patch(self):
        """Patch import functions."""
        self._monkeypatch.setattr(builtins, '__import__', self.fake_import)
        self._monkeypatch.setattr(
            importlib, 'import_module', self.fake_importlib_import)

    def _do_import(self, name):
        """Helper for fake_import and fake_importlib_import to do the work.

        Return:
            The imported fake module, or None if normal importing should be
            used.
        """
        if name not in self.modules:
            # Not one of the modules to test -> use real import
            return None
        elif self.modules[name]:
            ns = types.SimpleNamespace()
            if self.version_attribute is not None:
                setattr(ns, self.version_attribute, self.version)
            return ns
        else:
            raise ImportError("Fake ImportError for {}.".format(name))

    def fake_import(self, name, *args, **kwargs):
        """Fake for the builtin __import__."""
        module = self._do_import(name)
        if module is not None:
            return module
        else:
            return self._real_import(name, *args, **kwargs)

    def fake_importlib_import(self, name):
        """Fake for importlib.import_module."""
        module = self._do_import(name)
        if module is not None:
            return module
        else:
            return self._real_importlib_import(name)
