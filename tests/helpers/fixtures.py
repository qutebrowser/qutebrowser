# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import mimetypes
import os.path

import attr
import pytest
import py.path  # pylint: disable=no-name-in-module
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt5.QtNetwork import QNetworkCookieJar

import helpers.stubs as stubsmod
from qutebrowser.config import (config, configdata, configtypes, configexc,
                                configfiles, configcache, stylesheet)
from qutebrowser.api import config as configapi
from qutebrowser.utils import objreg, standarddir, utils, usertypes, qtutils
from qutebrowser.browser import greasemonkey, history, qutescheme
from qutebrowser.browser.webkit import cookies, cache
from qutebrowser.misc import savemanager, sql, objects, sessions
from qutebrowser.keyinput import modeman
from qutebrowser.qt import sip


_qute_scheme_handler = None


class WidgetContainer(QWidget):

    """Container for another widget."""

    def __init__(self, qtbot, parent=None):
        super().__init__(parent)
        self._qtbot = qtbot
        self.vbox = QVBoxLayout(self)
        qtbot.add_widget(self)
        self._widget = None

    def set_widget(self, widget):
        self.vbox.addWidget(widget)
        widget.container = self
        self._widget = widget

    def expose(self):
        with self._qtbot.waitExposed(self):
            self.show()
        self._widget.setFocus()


@pytest.fixture
def widget_container(qtbot):
    return WidgetContainer(qtbot)


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
def fake_statusbar(widget_container):
    """Fixture providing a statusbar in a container window."""
    widget_container.vbox.addStretch()
    statusbar = FakeStatusBar(widget_container)
    widget_container.set_widget(statusbar)
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
def greasemonkey_manager(monkeypatch, data_tmpdir):
    gm_manager = greasemonkey.GreasemonkeyManager()
    monkeypatch.setattr(greasemonkey, 'gm_manager', gm_manager)


@pytest.fixture(scope='session')
def testdata_scheme(qapp):
    try:
        global _qute_scheme_handler
        from qutebrowser.browser.webengine import webenginequtescheme
        from PyQt5.QtWebEngineWidgets import QWebEngineProfile
        webenginequtescheme.init()
        _qute_scheme_handler = webenginequtescheme.QuteSchemeHandler(
            parent=qapp)
        _qute_scheme_handler.install(QWebEngineProfile.defaultProfile())
    except ImportError:
        pass

    @qutescheme.add_handler('testdata')
    def handler(url):  # pylint: disable=unused-variable
        file_abs = os.path.abspath(os.path.dirname(__file__))
        filename = os.path.join(file_abs, os.pardir, 'end2end',
                                url.path().lstrip('/'))
        with open(filename, 'rb') as f:
            data = f.read()

        mimetype, _encoding = mimetypes.guess_type(filename)
        return mimetype, data


@pytest.fixture
def web_tab_setup(qtbot, tab_registry, session_manager_stub,
                  greasemonkey_manager, fake_args, config_stub,
                  testdata_scheme):
    """Shared setup for webkit_tab/webengine_tab."""
    # Make sure error logging via JS fails tests
    config_stub.val.content.javascript.log = {
        'info': 'info',
        'error': 'error',
        'unknown': 'error',
        'warning': 'error',
    }


@pytest.fixture
def webkit_tab(web_tab_setup, qtbot, cookiejar_and_cache, mode_manager,
               widget_container, download_stub, webpage):
    webkittab = pytest.importorskip('qutebrowser.browser.webkit.webkittab')

    tab = webkittab.WebKitTab(win_id=0, mode_manager=mode_manager,
                              private=False)
    widget_container.set_widget(tab)

    yield tab

    # Make sure the tab shuts itself down properly
    tab.private_api.shutdown()


@pytest.fixture
def webengine_tab(web_tab_setup, qtbot, redirect_webengine_data,
                  tabbed_browser_stubs, mode_manager, widget_container,
                  monkeypatch):
    tabwidget = tabbed_browser_stubs[0].widget
    tabwidget.current_index = 0
    tabwidget.index_of = 0

    webenginetab = pytest.importorskip(
        'qutebrowser.browser.webengine.webenginetab')

    tab = webenginetab.WebEngineTab(win_id=0, mode_manager=mode_manager,
                                    private=False)
    widget_container.set_widget(tab)

    yield tab

    # If a page is still loading here, _on_load_finished could get called
    # during teardown when session_manager_stub is already deleted.
    tab.stop()

    # Make sure the tab shuts itself down properly
    tab.private_api.shutdown()

    # If we wait for the GC to clean things up, there's a segfault inside
    # QtWebEngine sometimes (e.g. if we only run
    # tests/unit/browser/test_caret.py).
    # However, with Qt < 5.12, doing this here will lead to an immediate
    # segfault...
    monkeypatch.undo()  # version_check could be patched
    if qtutils.version_check('5.12'):
        sip.delete(tab._widget)


@pytest.fixture(params=['webkit', 'webengine'])
def web_tab(request):
    """A WebKitTab/WebEngineTab."""
    if request.param == 'webkit':
        pytest.importorskip('qutebrowser.browser.webkit.webkittab')
        return request.getfixturevalue('webkit_tab')
    elif request.param == 'webengine':
        pytest.importorskip('qutebrowser.browser.webengine.webenginetab')
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
def config_stub(stubs, monkeypatch, configdata_init, yaml_config_stub, qapp):
    """Fixture which provides a fake config object."""
    conf = config.Config(yaml_config=yaml_config_stub)
    monkeypatch.setattr(config, 'instance', conf)

    container = config.ConfigContainer(conf)
    monkeypatch.setattr(config, 'val', container)
    monkeypatch.setattr(configapi, 'val', container)

    cache = configcache.ConfigCache()
    monkeypatch.setattr(config, 'cache', cache)

    try:
        configtypes.FontBase.set_defaults(None, '10pt')
    except configexc.NoOptionError:
        # Completion tests patch configdata so fonts.default_family is
        # unavailable.
        pass

    conf.val = container  # For easier use in tests

    stylesheet.init()

    return conf


@pytest.fixture
def key_config_stub(config_stub, monkeypatch):
    """Fixture which provides a fake key config object."""
    keyconf = config.KeyConfig(config_stub)
    monkeypatch.setattr(config, 'key_instance', keyconf)
    return keyconf


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
def session_manager_stub(stubs, monkeypatch):
    """Fixture which provides a fake session-manager object."""
    stub = stubs.SessionManagerStub()
    monkeypatch.setattr(sessions, 'session_manager', stub)
    return stub


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
def webengineview(qtbot, monkeypatch, web_tab_setup):
    """Get a QWebEngineView if QtWebEngine is available."""
    QtWebEngineWidgets = pytest.importorskip('PyQt5.QtWebEngineWidgets')
    monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)
    view = QtWebEngineWidgets.QWebEngineView()
    qtbot.add_widget(view)
    return view


@pytest.fixture
def webpage(qnam):
    """Get a new QWebPage object."""
    QtWebKitWidgets = pytest.importorskip('PyQt5.QtWebKitWidgets')

    class WebPageStub(QtWebKitWidgets.QWebPage):

        """QWebPage with default error pages disabled."""

        def supportsExtension(self, _ext):
            """No extensions needed."""
            return False

    page = WebPageStub()

    page.networkAccessManager().deleteLater()
    page.setNetworkAccessManager(qnam)

    from qutebrowser.browser.webkit import webkitsettings
    webkitsettings._init_user_agent()

    return page


@pytest.fixture
def webview(qtbot, webpage, monkeypatch):
    """Get a new QWebView object."""
    QtWebKitWidgets = pytest.importorskip('PyQt5.QtWebKitWidgets')
    monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebKit)

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
def cookiejar_and_cache(stubs, monkeypatch):
    """Fixture providing a fake cookie jar and cache."""
    monkeypatch.setattr(cookies, 'cookie_jar', QNetworkCookieJar())
    monkeypatch.setattr(cookies, 'ram_cookie_jar', cookies.RAMCookieJar())
    monkeypatch.setattr(cache, 'diskcache', stubs.FakeNetworkCache())


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
def fake_args(request, monkeypatch):
    ns = types.SimpleNamespace()
    ns.backend = 'webengine' if request.config.webengine else 'webkit'
    ns.debug_flags = []

    monkeypatch.setattr(objects, 'args', ns)
    return ns


@pytest.fixture
def mode_manager(win_registry, config_stub, key_config_stub, qapp):
    mm = modeman.init(win_id=0, parent=qapp)
    yield mm
    objreg.delete('mode-manager', scope='window', window=0)


def standarddir_tmpdir(folder, monkeypatch, tmpdir):
    """Set tmpdir/config as the configdir.

    Use this to avoid creating a 'real' config dir (~/.config/qute_test).
    """
    confdir = tmpdir / folder
    confdir.ensure(dir=True)
    if hasattr(standarddir, folder):
        monkeypatch.setattr(standarddir, folder,
                            lambda **_kwargs: str(confdir))
    return confdir


@pytest.fixture
def download_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/download as the downloaddir.

    Use this to avoid creating a 'real' download dir (~/.config/qute_test).
    """
    return standarddir_tmpdir('download', monkeypatch, tmpdir)


@pytest.fixture
def config_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/config as the configdir.

    Use this to avoid creating a 'real' config dir (~/.config/qute_test).
    """
    monkeypatch.setattr(
        standarddir, 'config_py',
        lambda **_kwargs: str(tmpdir / 'config' / 'config.py'))
    return standarddir_tmpdir('config', monkeypatch, tmpdir)


@pytest.fixture
def config_py_arg(tmpdir, monkeypatch):
    """Set the config_py arg with a custom value for init."""
    f = tmpdir / 'temp_config.py'
    monkeypatch.setattr(
        standarddir, 'config_py',
        lambda **_kwargs: str(f))
    return f


@pytest.fixture
def data_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/data as the datadir.

    Use this to avoid creating a 'real' data dir (~/.local/share/qute_test).
    """
    return standarddir_tmpdir('data', monkeypatch, tmpdir)


@pytest.fixture
def runtime_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/runtime as the runtime dir.

    Use this to avoid creating a 'real' runtime dir.
    """
    return standarddir_tmpdir('runtime', monkeypatch, tmpdir)


@pytest.fixture
def cache_tmpdir(monkeypatch, tmpdir):
    """Set tmpdir/cache as the cachedir.

    Use this to avoid creating a 'real' cache dir (~/.cache/qute_test).
    """
    return standarddir_tmpdir('cache', monkeypatch, tmpdir)


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


@pytest.fixture
def web_history(fake_save_manager, tmpdir, init_sql, config_stub, stubs,
                monkeypatch):
    """Create a WebHistory object."""
    config_stub.val.completion.timestamp_format = '%Y-%m-%d'
    config_stub.val.completion.web_history.max_items = -1
    web_history = history.WebHistory(stubs.FakeHistoryProgress())
    monkeypatch.setattr(history, 'web_history', web_history)
    return web_history
