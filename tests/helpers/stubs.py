# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=invalid-name

"""Fake objects/stubs."""

import collections
from unittest import mock

from PyQt5.QtCore import pyqtSignal, QPoint, QProcess, QObject
from PyQt5.QtNetwork import (QNetworkRequest, QAbstractNetworkCache,
                             QNetworkCacheMetaData)
from PyQt5.QtWidgets import QCommonStyle, QWidget

from qutebrowser.browser.webkit import webview
from qutebrowser.config import configexc
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

    """A stub for QWebFrame.

    Attributes:
        focus_elem: The 'focused' element.
    """

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
        self.focus_elem = None
        self.toPlainText = mock.Mock(return_value=plaintext)
        self.toHtml = mock.Mock(return_value=html)
        self.zoomFactor = mock.Mock(return_value=zoom)

    def findFirstElement(self, selector):
        if selector == '*:focus':
            if self.focus_elem is not None:
                return self.focus_elem
            else:
                raise Exception("Trying to get focus element but it's unset!")
        else:
            raise Exception("Unknown selector {!r}!".format(selector))


class FakeChildrenFrame:

    """A stub for QWebFrame to test get_child_frames."""

    def __init__(self, children=None):
        if children is None:
            children = []
        self.childFrames = mock.Mock(return_value=children)


class FakeQApplication:

    """Stub to insert as QApplication module."""

    def __init__(self, style=None, all_widgets=None, active_window=None):
        self.instance = mock.Mock(return_value=self)

        self.style = mock.Mock(spec=QCommonStyle)
        self.style().metaObject().className.return_value = style

        self.allWidgets = lambda: all_widgets
        self.activeWindow = lambda: active_window


class FakeUrl:

    """QUrl stub which provides .path(), isValid() and host()."""

    def __init__(self, path=None, valid=True, host=None):
        self.path = mock.Mock(return_value=path)
        self.isValid = mock.Mock(returl_value=valid)
        self.host = mock.Mock(returl_value=host)


class FakeNetworkReply:

    """QNetworkReply stub which provides a Content-Disposition header."""

    KNOWN_HEADERS = {
        QNetworkRequest.ContentTypeHeader: 'Content-Type',
    }

    def __init__(self, headers=None, url=None):
        if url is None:
            url = FakeUrl()
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
    for attr in ['NormalExit', 'CrashExit', 'FailedToStart', 'Crashed',
                 'Timedout', 'WriteError', 'ReadError', 'UnknownError']:
        setattr(m, attr, getattr(QProcess, attr))
    return m


class FakeWebView(QWidget):

    """Fake WebView which can be added to a tab."""

    url_text_changed = pyqtSignal(str)
    shutting_down = pyqtSignal()

    def __init__(self, url=FakeUrl(), title='', tab_id=0):
        super().__init__()
        self.progress = 0
        self.scroll_pos = (-1, -1)
        self.load_status = webview.LoadStatus.none
        self.tab_id = tab_id
        self.cur_url = url
        self.title = title

    def url(self):
        return self.cur_url


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


class FakeCmdUtils:

    """Stub for cmdutils which provides a cmd_dict."""

    def __init__(self, commands):
        self.cmd_dict = commands


class FakeCommand:

    """A simple command stub which has a description."""

    def __init__(self, name='', desc='', hide=False, debug=False,
                 deprecated=False):
        self.desc = desc
        self.name = name
        self.hide = hide
        self.debug = debug
        self.deprecated = deprecated


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

    def start(self):
        self._started = True

    def stop(self):
        self._started = False

    def isActive(self):
        return self._started


class FakeConfigSection:

    """A stub for a KeyValue entry in configdata.DATA."""

    def __init__(self, *entries):
        self.values = collections.OrderedDict()
        self.descriptions = {}
        for name, value, desc in entries:
            self.values[name] = value
            self.descriptions[name] = desc

    def __iter__(self):
        """Iterate over all set values."""
        return self.values.__iter__()

    def __getitem__(self, key):
        return self.values[key]


class FakeSettingValue:

    """A stub for a SettingValue entry in configdata.DATA[section]."""

    def __init__(self, valid_values, default=None):
        self.typ = FakeConfigType(valid_values)
        self.default = lambda: default


class FakeConfigType:

    """A stub for the typ attribute of a FakeSettingValue."""

    def __init__(self, valid_values):
        # normally valid_values would be a ValidValues, but for simplicity of
        # testing this can be a simple list: [(val, desc), (val, desc), ...]
        self.complete = lambda: [(val, '') for val in valid_values]


class ConfigStub(QObject):

    """Stub for the config module.

    Attributes:
        data: The config data to return.
    """

    changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        """Constructor.

        Args:
            signal: The signal to use for self.changed.
        """
        super().__init__(parent)
        self.data = {}

    def __getitem__(self, name):
        return self.section(name)

    def section(self, name):
        """Get a section from the config.

        Args:
            name: The section name to get.

        Return:
            The section as dict.
        """
        return self.data[name]

    def get(self, sect, opt, raw=True):
        """Get a value from the config."""
        data = self.data[sect]
        try:
            return data[opt]
        except KeyError:
            raise configexc.NoOptionError(opt, sect)

    def set(self, sect, opt, value):
        """Set a value in the config."""
        data = self.data[sect]
        try:
            data[opt] = value
            self.changed.emit(sect, opt)
        except KeyError:
            raise configexc.NoOptionError(opt, sect)


class KeyConfigStub:

    """Stub for the key-config object."""

    def __init__(self):
        self.bindings = {}

    def get_bindings_for(self, section):
        return self.bindings.get(section)

    def set_bindings_for(self, section, bindings):
        self.bindings[section] = bindings


class FakeHistoryEntry:

    """Mock for webkit.history.Entry."""

    def __init__(self, atime, url, title, redirect=False):
        self.atime = float(atime)
        self.url = url
        self.title = title
        self.redirect = redirect


class UrlMarkManagerStub(QObject):

    """Stub for the quickmark-manager or bookmark-manager object."""

    added = pyqtSignal(str, str)
    removed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.marks = {}


class WebHistoryStub(QObject):

    """Stub for the web-history object."""

    add_completion_item = pyqtSignal(FakeHistoryEntry)
    cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_dict = collections.OrderedDict()

    def __iter__(self):
        return iter(self.history_dict.values())

    def __len__(self):
        return len(self.history_dict)


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

    new_tab = pyqtSignal(webview.WebView, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = []
        self.shutting_down = False

    def count(self):
        return len(self.tabs)

    def widget(self, i):
        return self.tabs[i]

    def page_title(self, i):
        return self.tabs[i].title

    def on_tab_close_requested(self, idx):
        del self.tabs[idx]


class ApplicationStub(QObject):

    """Stub to insert as the app object in objreg."""

    new_window = pyqtSignal(mainwindow.MainWindow)

    def __init__(self):
        super().__init__()
