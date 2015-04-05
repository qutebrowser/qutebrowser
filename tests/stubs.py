# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import logging

from unittest import mock

from PyQt5.QtCore import pyqtSignal, QPoint, QProcess, QObject
from PyQt5.QtNetwork import QNetworkRequest

from qutebrowser.config import configexc


class ConfigStub:

    """Stub for basekeyparser.config.

    Attributes:
        data: The config data to return.
    """

    def __init__(self, data=None):
        self.data = data or {}

    def section(self, name):
        """Get a section from the config.

        Args:
            name: The section name to get.

        Return:
            The section as dict.
        """
        return self.data[name]

    def get(self, sect, opt):
        """Get a value from the config."""
        data = self.data[sect]
        try:
            return data[opt]
        except KeyError:
            raise configexc.NoOptionError(opt, sect)


class FakeKeyEvent:

    """Fake QKeyPressEvent stub."""

    def __init__(self, key, modifiers=0, text=''):
        self.key = mock.Mock(return_value=key)
        self.text = mock.Mock(return_value=text)
        self.modifiers = mock.Mock(return_value=modifiers)


class FakeWebFrame:

    """A stub for QWebFrame."""

    def __init__(self, geometry, scroll=None, parent=None):
        """Constructor.

        Args:
            geometry: The geometry of the frame as QRect.
            scroll: The scroll position as QPoint.
            parent: The parent frame.
        """
        if scroll is None:
            scroll = QPoint(0, 0)
        self.geometry = mock.Mock(return_value=geometry)
        self.scrollPosition = mock.Mock(return_value=scroll)
        self.parentFrame = mock.Mock(return_value=parent)


class FakeChildrenFrame:

    """A stub for QWebFrame to test get_child_frames."""

    def __init__(self, children=None):
        if children is None:
            children = []
        self.childFrames = mock.Mock(return_value=children)


class FakeQApplication:

    """Stub to insert as QApplication module."""

    def __init__(self):
        self.instance = mock.Mock(return_value=self)


class FakeUrl:

    """QUrl stub which provides .path()."""

    def __init__(self, path=None):
        self.path = mock.Mock(return_value=path)


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


class FakeQProcess(mock.Mock):

    """QProcess stub.

    Gets some enum values from the real QProcess.
    """

    NormalExit = QProcess.NormalExit
    CrashExit = QProcess.CrashExit

    FailedToStart = QProcess.FailedToStart
    Crashed = QProcess.Crashed
    Timedout = QProcess.Timedout
    WriteError = QProcess.WriteError
    ReadError = QProcess.ReadError
    UnknownError = QProcess.UnknownError


class FakeSignal:

    """Fake pyqtSignal stub which uses a mock to see if it was called."""

    def __init__(self, name='fake'):
        self.signal = '2{}(int, int)'.format(name)


class FakeCmdUtils:

    """Stub for cmdutils which provides a cmd_dict."""

    def __init__(self, commands):
        self.cmd_dict = commands


class FakeCommand:

    """A simple command stub which has a description."""

    def __init__(self, desc):
        self.desc = desc


class FakeTimer(QObject):

    """Stub for a usertypes.Timer."""

    # pylint: disable=missing-docstring

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


class MessageModule:

    """A drop-in replacement for qutebrowser.utils.message."""

    def error(self, _win_id, message, _immediately=False):
        """Log an error to the message logger."""
        logging.getLogger('message').error(message)

    def warning(self, _win_id, message, _immediately=False):
        """Log a warning to the message logger."""
        logging.getLogger('message').warning(message)

    def info(self, _win_id, message, _immediately=True):
        """Log an info message to the message logger."""
        logging.getLogger('message').info(message)
