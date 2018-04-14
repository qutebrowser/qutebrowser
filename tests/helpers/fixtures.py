# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""pytest fixtures used by the whole testsuite.

See https://pytest.org/latest/fixture.html
"""


import sys
import tempfile
import itertools
import textwrap
import unittest.mock
import types

import attr
import pytest
import py.path  # pylint: disable=no-name-in-module
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt5.QtNetwork import QNetworkCookieJar

import helpers.stubs as stubsmod
import helpers.utils
from qutebrowser.config import (config, configdata, configtypes, configexc,
                                configfiles)
from qutebrowser.utils import objreg, standarddir, utils
from qutebrowser.browser import greasemonkey
from qutebrowser.browser.webkit import cookies
from qutebrowser.misc import savemanager, sql
from qutebrowser.keyinput import modeman


class WinRegistryHelper:

    """Helper class for win_registry."""

    @attr.s
    class FakeWindow:

        """A fake window object for the registry."""

        registry = attr.ib()

        def windowTitle(self):
            return 'window title - qutebrowser'

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


@pytest.fixture
def callback_checker(qtbot):
    return helpers.utils.CallbackChecker(qtbot)


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
    # pylint: enable=attribute-defined-outside-init

    with qtbot.waitExposed(container):
        container.show()
    return statusbar


@pytest.fixture
def win_registry():
    """Fixture providing a window registry for win_id 0 and 1."""
    helper = WinRegistryHelper()
    helper.add_window(0)
    yield helper
    helper.cleanup()


@pytest.fixture
def tab_registry(win_registry):
    """Fixture providing a tab registry for win_id 0."""
    registry = objreg.ObjectRegistry()
    objreg.register('tab-registry', registry, scope='window', window=0)
    yield registry
    objreg.delete('tab-registry', scope='window', window=0)


@pytest.fixture
def fake_web_tab(stubs, tab_registry, mode_manager, qapp):
    """Fixture providing the FakeWebTab *class*."""
    return stubs.FakeWebTab


@pytest.fixture
def greasemonkey_manager(data_tmpdir):
    gm_manager = greasemonkey.GreasemonkeyManager()
    objreg.register('greasemonkey', gm_manager)
    yield
    objreg.delete('greasemonkey')


@pytest.fixture
def webkit_tab(qtbot, tab_registry, cookiejar_and_cache, mode_manager,
               session_manager_stub, greasemonkey_manager):
    webkittab = pytest.importorskip('qutebrowser.browser.webkit.webkittab')
    tab = webkittab.WebKitTab(win_id=0, mode_manager=mode_manager,
                              private=False)
    qtbot.add_widget(tab)
    return tab


@pytest.fixture
def webengine_tab(qtbot, tab_registry, fake_args, mode_manager,
                  session_manager_stub, greasemonkey_manager,
                  redirect_webengine_data):
    webenginetab = pytest.importorskip(
        'qutebrowser.browser.webengine.webenginetab')
    tab = webenginetab.WebEngineTab(win_id=0, mode_manager=mode_manager,
                                    private=False)
    qtbot.add_widget(tab)
    return tab


@pytest.fixture(params=['webkit', 'webengine'])
def web_tab(request):
    """A WebKitTab/WebEngineTab."""
    if request.param == 'webkit':
        return request.getfixturevalue('webkit_tab')
    elif request.param == 'webengine':
        return request.getfixturevalue('webengine_tab')
    else:
        raise utils.Unreachable


def _generate_cmdline_tests():
    """Generate testcases for test_split_binding."""
    @attr.s
    class TestCase:

        cmd = attr.ib()
        valid = attr.ib()

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
    return request.param


@pytest.fixture(scope='session')
def configdata_init():
    """Initialize configdata if needed."""
    if configdata.DATA is None:
        configdata.init()


@pytest.fixture
def yaml_config_stub(config_tmpdir):
    """Fixture which provides a YamlConfig object."""
    return configfiles.YamlConfig()


@pytest.fixture
def config_stub(stubs, monkeypatch, configdata_init, yaml_config_stub):
    """Fixture which provides a fake config object."""
    conf = config.Config(yaml_config=yaml_config_stub)
    monkeypatch.setattr(config, 'instance', conf)

    container = config.ConfigContainer(conf)
    monkeypatch.setattr(config, 'val', container)

    try:
        configtypes.Font.monospace_fonts = container.fonts.monospace
    except configexc.NoOptionError:
        # Completion tests patch configdata so fonts.monospace is unavailable.
        pass

    conf.val = container  # For easier use in tests
    return conf


@pytest.fixture
def key_config_stub(config_stub, monkeypatch):
    """Fixture which provides a fake key config object."""
    keyconf = config.KeyConfig(config_stub)
    monkeypatch.setattr(config, 'key_instance', keyconf)
    return keyconf


@pytest.fixture
def host_blocker_stub(stubs):
    """Fixture which provides a fake host blocker object."""
    stub = stubs.HostBlockerStub()
    objreg.register('host-blocker', stub)
    yield stub
    objreg.delete('host-blocker')


@pytest.fixture
def quickmark_manager_stub(stubs):
    """Fixture which provides a fake quickmark manager object."""
    stub = stubs.QuickmarkManagerStub()
    objreg.register('quickmark-manager', stub)
    yield stub
    objreg.delete('quickmark-manager')


@pytest.fixture
def bookmark_manager_stub(stubs):
    """Fixture which provides a fake bookmark manager object."""
    stub = stubs.BookmarkManagerStub()
    objreg.register('bookmark-manager', stub)
    yield stub
    objreg.delete('bookmark-manager')


@pytest.fixture
def session_manager_stub(stubs):
    """Fixture which provides a fake session-manager object."""
    stub = stubs.SessionManagerStub()
    objreg.register('session-manager', stub)
    yield stub
    objreg.delete('session-manager')


@pytest.fixture
def tabbed_browser_stubs(qapp, stubs, win_registry):
    """Fixture providing a fake tabbed-browser object on win_id 0 and 1."""
    win_registry.add_window(1)
    stubs = [stubs.TabbedBrowserStub(), stubs.TabbedBrowserStub()]
    objreg.register('tabbed-browser', stubs[0], scope='window', window=0)
    objreg.register('tabbed-browser', stubs[1], scope='window', window=1)
    yield stubs
    objreg.delete('tabbed-browser', scope='window', window=0)
    objreg.delete('tabbed-browser', scope='window', window=1)


@pytest.fixture
def app_stub(stubs):
    """Fixture which provides a fake app object."""
    stub = stubs.ApplicationStub()
    objreg.register('app', stub)
    yield stub
    objreg.delete('app')


@pytest.fixture
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
def webengineview(qtbot):
    """Get a QWebEngineView if QtWebEngine is available."""
    QtWebEngineWidgets = pytest.importorskip('PyQt5.QtWebEngineWidgets')
    view = QtWebEngineWidgets.QWebEngineView()
    qtbot.add_widget(view)
    return view


@pytest.fixture
def webpage(qnam):
    """Get a new QWebPage object."""
    QtWebKitWidgets = pytest.importorskip('PyQt5.QtWebKitWidgets')
    page = QtWebKitWidgets.QWebPage()
    page.networkAccessManager().deleteLater()
    page.setNetworkAccessManager(qnam)
    return page


@pytest.fixture
def webview(qtbot, webpage):
    """Get a new QWebView object."""
    QtWebKitWidgets = pytest.importorskip('PyQt5.QtWebKitWidgets')

    view = QtWebKitWidgets.QWebView()
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


@pytest.fixture
def fake_save_manager():
    """Create a mock of save-manager and register it into objreg."""
    fake_save_manager = unittest.mock.Mock(spec=savemanager.SaveManager)
    objreg.register('save-manager', fake_save_manager)
    yield fake_save_manager
    objreg.delete('save-manager')


@pytest.fixture
def fake_args(request):
    ns = types.SimpleNamespace()
    ns.backend = 'webengine' if request.config.webengine else 'webkit'
    objreg.register('args', ns)
    yield ns
    objreg.delete('args')


@pytest.fixture
def mode_manager(win_registry, config_stub, qapp):
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
    confdir.ensure(dir=True)
    monkeypatch.setattr(standarddir, 'config', lambda auto=False: str(confdir))
    return confdir


@pytest.fixture
def data_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/data as the datadir.

    Use this to avoid creating a 'real' data dir (~/.local/share/qute_test).
    """
    datadir = tmpdir / 'data'
    datadir.ensure(dir=True)
    monkeypatch.setattr(standarddir, 'data', lambda system=False: str(datadir))
    return datadir


@pytest.fixture
def runtime_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/runtime as the runtime dir.

    Use this to avoid creating a 'real' runtime dir.
    """
    runtimedir = tmpdir / 'runtime'
    runtimedir.ensure(dir=True)
    monkeypatch.setattr(standarddir, 'runtime', lambda: str(runtimedir))
    return runtimedir


@pytest.fixture
def cache_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/cache as the cachedir.

    Use this to avoid creating a 'real' cache dir (~/.cache/qute_test).
    """
    cachedir = tmpdir / 'cache'
    cachedir.ensure(dir=True)
    monkeypatch.setattr(standarddir, 'cache', lambda: str(cachedir))
    return cachedir


@pytest.fixture
def redirect_webengine_data(data_tmpdir, monkeypatch):
    """Set XDG_DATA_HOME and HOME to a temp location.

    While data_tmpdir covers most cases by redirecting standarddir.data(), this
    is not enough for places QtWebEngine references the data dir internally.
    For these, we need to set the environment variable to redirect data access.

    We also set HOME as in some places, the home directory is used directly...
    """
    monkeypatch.setenv('XDG_DATA_HOME', str(data_tmpdir))
    monkeypatch.setenv('HOME', str(data_tmpdir))


@pytest.fixture()
def short_tmpdir():
    """A short temporary directory for a XDG_RUNTIME_DIR."""
    with tempfile.TemporaryDirectory() as tdir:
        yield py.path.local(tdir)  # pylint: disable=no-member


@pytest.fixture
def init_sql(data_tmpdir):
    """Initialize the SQL module, and shut it down after the test."""
    path = str(data_tmpdir / 'test.db')
    sql.init(path)
    yield
    sql.close()


class ModelValidator:

    """Validates completion models."""

    def __init__(self, modeltester):
        modeltester.data_display_may_return_none = True
        self._model = None
        self._modeltester = modeltester

    def set_model(self, model):
        self._model = model
        self._modeltester.check(model)

    def validate(self, expected):
        assert self._model.rowCount() == len(expected)
        for row, items in enumerate(expected):
            for col, item in enumerate(items):
                assert self._model.data(self._model.index(row, col)) == item


@pytest.fixture
def model_validator(qtmodeltester):
    return ModelValidator(qtmodeltester)


@pytest.fixture
def download_stub(win_registry, tmpdir, stubs):
    """Register a FakeDownloadManager."""
    stub = stubs.FakeDownloadManager(tmpdir)
    objreg.register('qtnetwork-download-manager', stub)
    yield stub
    objreg.delete('qtnetwork-download-manager')
