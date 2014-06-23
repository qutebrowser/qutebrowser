# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from unittest.mock import Mock

from PyQt5.QtCore import QPoint, QProcess
from PyQt5.QtWebKit import QWebElement


class ConfigStub:

    """Stub for basekeyparser.config.

    Attributes:
        data: The config data to return.
    """

    class NoOptionError(Exception):

        """NoOptionError exception."""

        pass

    def __init__(self, data):
        self.data = data

    def section(self, name):
        """Get a section from the config.

        Args:
            name: The section name to get.

        Raise:
            ValueError if section isn't test1/test2.

        Return:
            The section as dict.
        """
        return self.data[name]

    def get(self, sect, opt):
        """Get a value from the config."""
        sect = self.data[sect]
        try:
            return sect[opt]
        except KeyError:
            raise self.NoOptionError


class FakeKeyEvent:

    """Fake QKeyPressEvent stub."""

    def __init__(self, key, modifiers=0, text=''):
        self.key = Mock(return_value=key)
        self.text = Mock(return_value=text)
        self.modifiers = Mock(return_value=modifiers)


class FakeWebElement:

    """A stub for QWebElement."""

    def __init__(self, geometry=None, frame=None, null=False, visibility='',
                 display='', attributes=None):
        """Constructor.

        Args:
            geometry: The geometry of the QWebElement as QRect.
            frame: The QWebFrame the element is in.
            null: Whether the element is null or not.
            visibility: The CSS visibility style property calue.
            display: The CSS display style property calue.
            attributes: Boolean HTML attributes to be added.

        Raise:
            ValueError if element is not null and geometry/frame are not given.
        """
        self.geometry = Mock(return_value=geometry)
        self.webFrame = Mock(return_value=frame)
        self.isNull = Mock(return_value=null)
        self._visibility = visibility
        self._display = display
        self._attributes = attributes

    def styleProperty(self, name, strategy):
        """Return the CSS style property named name.

        Only display/visibility and ComputedStyle are simulated.

        Raise:
            ValueError if strategy is not ComputedStyle or name is not
                       visibility/display.
        """
        if strategy != QWebElement.ComputedStyle:
            raise ValueError("styleProperty called with strategy != "
                             "ComputedStyle ({})!".format(strategy))
        if name == 'visibility':
            return self._visibility
        elif name == 'display':
            return self._display
        else:
            raise ValueError("styleProperty called with unknown name "
                             "'{}'".format(name))

    def hasAttribute(self, name):
        """Check if the element has an attribute named name."""
        if self._attributes is None:
            return False
        else:
            return name in self._attributes


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
        self.geometry = Mock(return_value=geometry)
        self.scrollPosition = Mock(return_value=scroll)
        self.parentFrame = Mock(return_value=parent)


class FakeChildrenFrame:

    """A stub for QWebFrame to test get_child_frames."""

    def __init__(self, children=None):
        if children is None:
            children = []
        self.childFrames = Mock(return_value=children)


class FakeQApplication:

    """Stub to insert as QApplication module."""

    def __init__(self, focus):
        # pylint: disable=invalid-name
        self.focusWidget = Mock(return_value=focus)
        self.instance = Mock(return_value=self)


class FakeUrl:

    """QUrl stub which provides .path()."""

    def __init__(self, path=None):
        self.path = Mock(return_value=path)


class FakeNetworkReply:

    """QNetworkReply stub which provides a Content-Disposition header."""

    def __init__(self, content_disposition=None, url=None):
        if url is None:
            url = FakeUrl()
        self._content_disposition = content_disposition
        self.url = Mock(return_value=url)

    def hasRawHeader(self, name):
        """Check if the reply has a certain header.

        Args:
            name: The name of the header.

        Return:
            True if the header is present, False if not.

        Raise:
            ValueError: If a header other than Content-Disposition is
                        requested.
        """
        if name == 'Content-Disposition':
            return self._content_disposition is not None
        else:
            raise ValueError("Invalid header {}".format(name))

    def rawHeader(self, name):
        """Get the raw header data of a header.

        Args:
            name: The name of the header.

        Return:
            The header data, as ISO-8859-1 encoded bytes() object.

        Raise:
            ValueError: If a header other than Content-Disposition is
                        requested.
        """
        if name != 'Content-Disposition':
            raise ValueError("Invalid header {}".format(name))
        cd = self._content_disposition
        if cd is None:
            raise ValueError("Content-Disposition is None!")
        return cd.encode('iso-8859-1')


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
        self.finished = Mock()
        self.error = Mock()
        self.start = Mock()


class FakeSignal:

    """Fake pyqtSignal stub which uses a mock to see if it was called."""

    def __init__(self, name='fake'):
        self.signal = '2{}(int, int)'.format(name)
