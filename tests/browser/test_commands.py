# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.browser.commands."""

import collections

import pytest
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QTabBar, QTabWidget
from PyQt5.QtNetwork import QNetworkCookieJar

from qutebrowser.browser import commands, cookies
from qutebrowser.mainwindow import tabbedbrowser
from qutebrowser.utils import objreg


ObjectsRet = collections.namedtuple('Dispatcher', ['tb', 'cd'])

FakeWindow = collections.namedtuple('FakeWindow', ['registry'])


@pytest.yield_fixture
def win_registry():
    """Fixture providing a window registry for win_id 0."""
    registry = objreg.ObjectRegistry()
    window = FakeWindow(registry)
    objreg.window_registry[0] = window
    yield registry
    del objreg.window_registry[0]


@pytest.yield_fixture
def tab_registry(win_registry):
    """Fixture providing a tab registry for win_id 0."""
    registry = objreg.ObjectRegistry()
    objreg.register('tab-registry', registry, scope='window', window=0)
    yield registry
    objreg.delete('tab-registry', scope='window', window=0)


@pytest.yield_fixture(autouse=True)
def ram_cookiejar():
    jar = QNetworkCookieJar()
    objreg.register('cookie-jar', jar)
    yield jar
    objreg.delete('cookie-jar')


@pytest.fixture
def objects(qtbot, config_stub, tab_registry):
    """Fixture providing a CommandDispatcher and a fake TabbedBrowser."""
    config_stub.data = {
        'general': {
            'auto-search': False,
        },
        'fonts': {
            'tabbar': QFont('Courier'),
        },
        'colors': {
            'tabs.bg.bar': QColor('black'),
        },
        'tabs': {
            'movable': False,
            'position': QTabWidget.North,
            'select-on-remove': QTabBar.SelectRightTab,
            'tabs-are-windows': False,
        },
        'ui': {
            'zoom-levels': [100],
            'default-zoom': 100,
        },
    }
    win_id = 0
    tabbed_browser = tabbedbrowser.TabbedBrowser(win_id)
    qtbot.add_widget(tabbed_browser)
    dispatcher = commands.CommandDispatcher(win_id, tabbed_browser)
    return ObjectsRet(tabbed_browser, dispatcher)


def test_openurl(objects):
    objects.cd.openurl('http://www.heise.de')
    #objects.tb_mock.
