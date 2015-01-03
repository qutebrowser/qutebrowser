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

from unittest import mock

from PyQt5.QtCore import QPoint, QProcess
from PyQt5.QtNetwork import QNetworkRequest

from qutebrowser.config import configexc


class ConfigStub:

    """Stub for basekeyparser.config.

    Attributes:
        data: The config data to return.
    """

    def __init__(self, data):
        self.data = data

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
            name: The name of the header.

        Return:
            True if the header is present, False if not.
        """
        return name in self.headers

    def rawHeader(self, name):
        """Get the raw header data of a header.

        Args:
            name: The name of the header.

        Return:
            The header data, as ISO-8859-1 encoded bytes() object.
        """
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


class FakeQProcess:

    """QProcess stub.

    Gets some enum values from the real QProcess and uses mocks for signals.
    """

    NormalExit = QProcess.NormalExit
    CrashExit = QProcess.CrashExit

    FailedToStart = QProcess.FailedToStart
    Crashed = QProcess.Crashed
    Timedout = QProcess.Timedout
    WriteError = QProcess.WriteError
    ReadError = QProcess.ReadError
    UnknownError = QProcess.UnknownError

    def __init__(self, parent=None):  # pylint: disable=unused-argument
        self.finished = mock.Mock()
        self.error = mock.Mock()
        self.start = mock.Mock()


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
