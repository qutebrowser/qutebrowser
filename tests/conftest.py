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

"""The qutebrowser test suite contest file."""

import pytest


@pytest.fixture(scope='session', autouse=True)
def app_and_logging(qapp):
    """Initialize a QApplication and logging.

    This ensures that a QApplication is created and used by all tests.
    """
    from log import init
    init()


@pytest.fixture(scope='session')
def stubs():
    """Provide access to stub objects useful for testing."""
    import stubs
    return stubs


@pytest.fixture(scope='session')
def unicode_encode_err():
    """Provide a fake UnicodeEncodeError exception."""
    return UnicodeEncodeError('ascii',  # codec
                              '',  # object
                              0,  # start
                              2,  # end
                              'fake exception')  # reason


@pytest.fixture
def webpage():
    """Get a new QWebPage object."""
    from PyQt5.QtWebKitWidgets import QWebPage
    from PyQt5.QtNetwork import QNetworkAccessManager

    page = QWebPage()
    nam = page.networkAccessManager()
    nam.setNetworkAccessible(QNetworkAccessManager.NotAccessible)
    return page


@pytest.fixture
def fake_keyevent_factory():
    """Fixture that when called will return a mock instance of a QKeyEvent."""
    from unittest import mock
    from PyQt5.QtGui import QKeyEvent

    def fake_keyevent(key, modifiers=0, text=''):
        """Generate a new fake QKeyPressEvent."""
        evtmock = mock.create_autospec(QKeyEvent, instance=True)
        evtmock.key.return_value = key
        evtmock.modifiers.return_value = modifiers
        evtmock.text.return_value = text
        return evtmock

    return fake_keyevent
