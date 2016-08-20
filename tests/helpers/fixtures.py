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


"""pytest fixtures used by the whole testsuite.

See https://pytest.org/latest/fixture.html
"""


import sys
import collections
import itertools
import textwrap
import unittest.mock
import types
import os

import pytest

import helpers.stubs as stubsmod
from qutebrowser.config import config
from qutebrowser.utils import objreg
from qutebrowser.browser.webkit import cookies
from qutebrowser.misc import savemanager
from qutebrowser.keyinput import modeman

from PyQt5.QtCore import PYQT_VERSION, pyqtSignal, QEvent, QSize, Qt, QObject
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt5.QtNetwork import QNetworkCookieJar
try:
    from PyQt5 import QtWebEngineWidgets
except ImportError as e:
    QtWebEngineWidgets = None


class WinRegistryHelper:

    """Helper class for win_registry."""

    FakeWindow = collections.namedtuple('FakeWindow', ['registry'])

    def __init__(self):
        self._ids = []

    def add_window(self, win_id):
        assert win_id not in objreg.window_registry
        registry = objreg.ObjectRegistry()
        window = self.FakeWindow(registry)
        objreg.window_registry[win_id] = window
        self._ids.append(win_id)

    def cleanup(self):
        for win_id in self._ids:
            del objreg.window_registry[win_id]


class CallbackChecker(QObject):

    """Check if a value provided by a callback is the expected one."""

    got_result = pyqtSignal(object)
    UNSET = object()

    def __init__(self, qtbot, parent=None):
        super().__init__(parent)
        self._qtbot = qtbot
        self._result = self.UNSET

    def callback(self, result):
        """Callback which can be passed to runJavaScript."""
        self._result = result
        self.got_result.emit(result)

    def check(self, expected):
        """Wait until the JS result arrived and compare it."""
        if self._result is self.UNSET:
            with self._qtbot.waitSignal(self.got_result):
                pass
        assert self._result == expected


@pytest.fixture
def callback_checker(qtbot):
    return CallbackChecker(qtbot)


class FakeStatusBar(QWidget):

    """Fake statusbar to test progressbar sizing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hbox = QHBoxLayout(self)
        self.hbox.addStretch()
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet('background-color: red;')

    def minimumSizeHint(self):
        return QSize(1, self.fontMetrics().height())


@pytest.fixture
def fake_statusbar(qtbot):
    """Fixture providing a statusbar in a container window."""
    container = QWidget()
    qtbot.add_widget(container)
    vbox = QVBoxLayout(container)
    vbox.addStretch()

    statusbar = FakeStatusBar(container)
    # to make sure container isn't GCed
    # pylint: disable=attribute-defined-outside-init
    statusbar.container = container
    vbox.addWidget(statusbar)

    container.show()
    qtbot.waitForWindowShown(container)
    return statusbar


@pytest.yield_fixture
def win_registry():
    """Fixture providing a window registry for win_id 0 and 1."""
    helper = WinRegistryHelper()
    helper.add_window(0)
    yield helper
    helper.cleanup()


@pytest.yield_fixture
def tab_registry(win_registry):
    """Fixture providing a tab registry for win_id 0."""
    registry = objreg.ObjectRegistry()
    objreg.register('tab-registry', registry, scope='window', window=0)
    yield registry
    objreg.delete('tab-registry', scope='window', window=0)


@pytest.fixture
def fake_web_tab(stubs, tab_registry, mode_manager, qapp):
    """Fixture providing the FakeWebTab *class*."""
    if PYQT_VERSION < 0x050600:
        pytest.skip('Causes segfaults, see #1638')
    return stubs.FakeWebTab


def _generate_cmdline_tests():
    """Generate testcases for test_split_binding."""
    # pylint: disable=invalid-name
    TestCase = collections.namedtuple('TestCase', 'cmd, valid')
    separators = [';;', ' ;; ', ';; ', ' ;;']
    invalid = ['foo', '']
    valid = ['leave-mode', 'hint all']
    # Valid command only -> valid
    for item in valid:
        yield TestCase(''.join(item), True)
    # Invalid command only -> invalid
    for item in invalid:
        yield TestCase(''.join(item), False)
    # Invalid command combined with invalid command -> invalid
    for item in itertools.product(invalid, separators, invalid):
        yield TestCase(''.join(item), False)
    # Valid command combined with valid command -> valid
    for item in itertools.product(valid, separators, valid):
        yield TestCase(''.join(item), True)
    # Valid command combined with invalid command -> invalid
    for item in itertools.product(valid, separators, invalid):
        yield TestCase(''.join(item), False)
    # Invalid command combined with valid command -> invalid
    for item in itertools.product(invalid, separators, valid):
        yield TestCase(''.join(item), False)
    # Command with no_cmd_split combined with an "invalid" command -> valid
    for item in itertools.product(['bind x open'], separators, invalid):
        yield TestCase(''.join(item), True)
    # Partial command
    yield TestCase('message-i', False)


@pytest.fixture(params=_generate_cmdline_tests(), ids=lambda e: e.cmd)
def cmdline_test(request):
    """Fixture which generates tests for things validating commandlines."""
    # Import qutebrowser.app so all cmdutils.register decorators get run.
    import qutebrowser.app  # pylint: disable=unused-variable
    return request.param


@pytest.yield_fixture
def config_stub(stubs):
    """Fixture which provides a fake config object."""
    stub = stubs.ConfigStub()
    objreg.register('config', stub)
    yield stub
    objreg.delete('config')


@pytest.yield_fixture
def default_config():
    """Fixture that provides and registers an empty default config object."""
    config_obj = config.ConfigManager()
    config_obj.read(configdir=None, fname=None, relaxed=True)
    objreg.register('config', config_obj)
    yield config_obj
    objreg.delete('config')


@pytest.yield_fixture
def key_config_stub(stubs):
    """Fixture which provides a fake key config object."""
    stub = stubs.KeyConfigStub()
    objreg.register('key-config', stub)
    yield stub
    objreg.delete('key-config')


@pytest.yield_fixture
def host_blocker_stub(stubs):
    """Fixture which provides a fake host blocker object."""
    stub = stubs.HostBlockerStub()
    objreg.register('host-blocker', stub)
    yield stub
    objreg.delete('host-blocker')


@pytest.yield_fixture
def quickmark_manager_stub(stubs):
    """Fixture which provides a fake quickmark manager object."""
    stub = stubs.QuickmarkManagerStub()
    objreg.register('quickmark-manager', stub)
    yield stub
    objreg.delete('quickmark-manager')


@pytest.yield_fixture
def bookmark_manager_stub(stubs):
    """Fixture which provides a fake bookmark manager object."""
    stub = stubs.BookmarkManagerStub()
    objreg.register('bookmark-manager', stub)
    yield stub
    objreg.delete('bookmark-manager')


@pytest.yield_fixture
def web_history_stub(stubs):
    """Fixture which provides a fake web-history object."""
    stub = stubs.WebHistoryStub()
    objreg.register('web-history', stub)
    yield stub
    objreg.delete('web-history')


@pytest.yield_fixture
def session_manager_stub(stubs):
    """Fixture which provides a fake web-history object."""
    stub = stubs.SessionManagerStub()
    objreg.register('session-manager', stub)
    yield stub
    objreg.delete('session-manager')


@pytest.yield_fixture
def tabbed_browser_stubs(stubs, win_registry):
    """Fixture providing a fake tabbed-browser object on win_id 0 and 1."""
    win_registry.add_window(1)
    stubs = [stubs.TabbedBrowserStub(), stubs.TabbedBrowserStub()]
    objreg.register('tabbed-browser', stubs[0], scope='window', window=0)
    objreg.register('tabbed-browser', stubs[1], scope='window', window=1)
    yield stubs
    objreg.delete('tabbed-browser', scope='window', window=0)
    objreg.delete('tabbed-browser', scope='window', window=1)


@pytest.yield_fixture
def app_stub(stubs):
    """Fixture which provides a fake app object."""
    stub = stubs.ApplicationStub()
    objreg.register('app', stub)
    yield stub
    objreg.delete('app')


@pytest.yield_fixture
def status_command_stub(stubs, qtbot, win_registry):
    """Fixture which provides a fake status-command object."""
    cmd = stubs.StatusBarCommandStub()
    objreg.register('status-command', cmd, scope='window', window=0)
    qtbot.addWidget(cmd)
    yield cmd
    objreg.delete('status-command', scope='window', window=0)


@pytest.fixture(scope='session')
def stubs():
    """Provide access to stub objects useful for testing."""
    return stubsmod


@pytest.fixture(scope='session')
def unicode_encode_err():
    """Provide a fake UnicodeEncodeError exception."""
    return UnicodeEncodeError('ascii',  # codec
                              '',  # object
                              0,  # start
                              2,  # end
                              'fake exception')  # reason


@pytest.fixture(scope='session')
def qnam(qapp):
    """Session-wide QNetworkAccessManager."""
    from PyQt5.QtNetwork import QNetworkAccessManager
    nam = QNetworkAccessManager()
    nam.setNetworkAccessible(QNetworkAccessManager.NotAccessible)
    return nam


@pytest.fixture
def webengineview():
    """Get a QWebEngineView if QtWebEngine is available."""
    if QtWebEngineWidgets is None:
        pytest.skip("QtWebEngine unavailable")
    return QtWebEngineWidgets.QWebEngineView()


@pytest.fixture
def webpage(qnam):
    """Get a new QWebPage object."""
    from PyQt5.QtWebKitWidgets import QWebPage

    page = QWebPage()
    page.networkAccessManager().deleteLater()
    page.setNetworkAccessManager(qnam)
    return page


@pytest.fixture
def webview(qtbot, webpage):
    """Get a new QWebView object."""
    from PyQt5.QtWebKitWidgets import QWebView

    view = QWebView()
    qtbot.add_widget(view)

    view.page().deleteLater()
    view.setPage(webpage)

    view.resize(640, 480)
    return view


@pytest.fixture
def webframe(webpage):
    """Convenience fixture to get a mainFrame of a QWebPage."""
    return webpage.mainFrame()


@pytest.fixture
def fake_keyevent_factory():
    """Fixture that when called will return a mock instance of a QKeyEvent."""
    def fake_keyevent(key, modifiers=0, text='', typ=QEvent.KeyPress):
        """Generate a new fake QKeyPressEvent."""
        evtmock = unittest.mock.create_autospec(QKeyEvent, instance=True)
        evtmock.key.return_value = key
        evtmock.modifiers.return_value = modifiers
        evtmock.text.return_value = text
        evtmock.type.return_value = typ
        return evtmock

    return fake_keyevent


@pytest.yield_fixture
def cookiejar_and_cache(stubs):
    """Fixture providing a fake cookie jar and cache."""
    jar = QNetworkCookieJar()
    ram_jar = cookies.RAMCookieJar()
    cache = stubs.FakeNetworkCache()
    objreg.register('cookie-jar', jar)
    objreg.register('ram-cookie-jar', ram_jar)
    objreg.register('cache', cache)
    yield
    objreg.delete('cookie-jar')
    objreg.delete('ram-cookie-jar')
    objreg.delete('cache')


@pytest.fixture
def py_proc():
    """Get a python executable and args list which executes the given code."""
    if getattr(sys, 'frozen', False):
        pytest.skip("Can't be run when frozen")

    def func(code):
        return (sys.executable, ['-c', textwrap.dedent(code.strip('\n'))])

    return func


@pytest.yield_fixture
def fake_save_manager():
    """Create a mock of save-manager and register it into objreg."""
    fake_save_manager = unittest.mock.Mock(spec=savemanager.SaveManager)
    objreg.register('save-manager', fake_save_manager)
    yield fake_save_manager
    objreg.delete('save-manager')


@pytest.yield_fixture
def fake_args():
    ns = types.SimpleNamespace()
    objreg.register('args', ns)
    yield ns
    objreg.delete('args')


@pytest.yield_fixture
def mode_manager(win_registry, config_stub, qapp):
    config_stub.data.update({'input': {'forward-unbound-keys': 'auto'}})
    mm = modeman.ModeManager(0)
    objreg.register('mode-manager', mm, scope='window', window=0)
    yield mm
    objreg.delete('mode-manager', scope='window', window=0)


@pytest.fixture
def config_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/config as the configdir.

    Use this to avoid creating a 'real' config dir (~/.config/qute_test).
    """
    confdir = tmpdir / 'config'
    path = str(confdir)
    os.mkdir(path)
    monkeypatch.setattr('qutebrowser.utils.standarddir.config', lambda: path)
    return confdir


@pytest.fixture
def data_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/data as the datadir.

    Use this to avoid creating a 'real' data dir (~/.local/share/qute_test).
    """
    datadir = tmpdir / 'data'
    path = str(datadir)
    os.mkdir(path)
    monkeypatch.setattr('qutebrowser.utils.standarddir.data', lambda: path)
    return datadir


@pytest.fixture
def redirect_xdg_data(data_tmpdir, monkeypatch):
    """Set XDG_DATA_HOME to a temp location.

    While data_tmpdir covers most cases by redirecting standarddir.data(), this
    is not enough for places Qt references the data dir internally. For these,
    we need to set the environment variable to redirect data access.
    """
    monkeypatch.setenv('XDG_DATA_HOME', str(data_tmpdir))
