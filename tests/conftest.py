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

# pylint: disable=unused-import

"""The qutebrowser test suite conftest file."""

import os
import sys
import collections
import itertools
import logging
import textwrap
import warnings

import pytest
import hypothesis

import helpers.stubs as stubsmod
from helpers import logfail
from helpers.logfail import fail_on_logging
from helpers.messagemock import message_mock
from qutebrowser.config import config
from qutebrowser.utils import objreg

from PyQt5.QtCore import QEvent, QSize, Qt, PYQT_VERSION
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt5.QtNetwork import QNetworkCookieJar
import xvfbwrapper


# Set hypothesis settings
hypothesis.settings.register_profile('default',
                                     hypothesis.settings(strict=True))
hypothesis.settings.load_profile('default')


def _apply_platform_markers(item):
    """Apply a skip marker to a given item."""
    markers = [
        ('posix', os.name != 'posix', "Requires a POSIX os"),
        ('windows', os.name != 'nt', "Requires Windows"),
        ('linux', not sys.platform.startswith('linux'), "Requires Linux"),
        ('osx', sys.platform != 'darwin', "Requires OS X"),
        ('not_osx', sys.platform == 'darwin', "Skipped on OS X"),
        ('not_frozen', getattr(sys, 'frozen', False),
            "Can't be run when frozen"),
        ('frozen', not getattr(sys, 'frozen', False),
            "Can only run when frozen"),
        ('not_xvfb', item.config.xvfb_display is not None,
            "Can't be run with Xvfb."),
        ('skip', True, "Always skipped."),
        ('pyqt531_or_newer', PYQT_VERSION < 0x050301,
            "Needs PyQt 5.3.1 or newer"),
    ]

    for searched_marker, condition, default_reason in markers:
        marker = item.get_marker(searched_marker)
        if not marker or not condition:
            continue

        if 'reason' in marker.kwargs:
            reason = '{}: {}'.format(default_reason,
                                        marker.kwargs['reason'])
            del marker.kwargs['reason']
        else:
            reason = default_reason + '.'
        skipif_marker = pytest.mark.skipif(condition, *marker.args,
                                           reason=reason, **marker.kwargs)
        item.add_marker(skipif_marker)


def pytest_collection_modifyitems(items):
    """Handle custom markers.

    pytest hook called after collection has been performed.

    Adds a marker named "gui" which can be used to filter gui tests from the
    command line.

    For example:

        py.test -m "not gui"  # run all tests except gui tests
        py.test -m "gui"  # run only gui tests

    It also handles the platform specific markers by translating them to skipif
    markers.

    Args:
        items: list of _pytest.main.Node items, where each item represents
               a python test that will be executed.

    Reference:
        http://pytest.org/latest/plugins.html
    """
    for item in items:
        if 'qapp' in getattr(item, 'fixturenames', ()):
            item.add_marker('gui')
            if sys.platform == 'linux' and not os.environ.get('DISPLAY', ''):
                if ('CI' in os.environ and
                        not os.environ.get('QUTE_NO_DISPLAY', '')):
                    raise Exception("No display available on CI!")
                skip_marker = pytest.mark.skipif(
                    True, reason="No DISPLAY available")
                item.add_marker(skip_marker)

        if hasattr(item, 'module'):
            module_path = os.path.relpath(
                item.module.__file__,
                os.path.commonprefix([__file__, item.module.__file__]))

            module_root_dir = os.path.split(module_path)[0]
            if module_root_dir == 'integration':
                item.add_marker(pytest.mark.integration)

        _apply_platform_markers(item)
        if item.get_marker('xfail_norun'):
            item.add_marker(pytest.mark.xfail(run=False))


def pytest_ignore_collect(path):
    """Ignore BDD tests during collection if frozen."""
    rel_path = path.relto(os.path.dirname(__file__))
    return (rel_path == os.path.join('integration', 'features') and
            hasattr(sys, 'frozen'))


@pytest.fixture(scope='session')
def qapp(qapp):
    """Change the name of the QApplication instance."""
    qapp.setApplicationName('qute_test')
    return qapp


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


@pytest.fixture(params=_generate_cmdline_tests(), ids=lambda e: e.cmd)
def cmdline_test(request):
    """Fixture which generates tests for things validating commandlines."""
    # Import qutebrowser.app so all cmdutils.register decorators get run.
    import qutebrowser.app
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
    config_obj = config.ConfigManager(configdir=None, fname=None, relaxed=True)
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
    from unittest import mock
    from PyQt5.QtGui import QKeyEvent

    def fake_keyevent(key, modifiers=0, text='', typ=QEvent.KeyPress):
        """Generate a new fake QKeyPressEvent."""
        evtmock = mock.create_autospec(QKeyEvent, instance=True)
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
    cache = stubs.FakeNetworkCache()
    objreg.register('cookie-jar', jar)
    objreg.register('cache', cache)
    yield
    objreg.delete('cookie-jar')
    objreg.delete('cache')


@pytest.fixture
def py_proc():
    """Get a python executable and args list which executes the given code."""
    if getattr(sys, 'frozen', False):
        pytest.skip("Can't be run when frozen")
    def func(code):
        return (sys.executable, ['-c', textwrap.dedent(code.strip('\n'))])
    return func


@pytest.yield_fixture(autouse=True)
def fail_tests_on_warnings():
    warnings.simplefilter('error')
    yield
    warnings.resetwarnings()


def pytest_addoption(parser):
    parser.addoption('--no-xvfb', action='store_true', default=False,
                     help='Disable xvfb in tests.')
    parser.addoption('--qute-delay', action='store', default=0, type=int,
                     help="Delay between qutebrowser commands.")


def pytest_configure(config):
    """Start Xvfb if we're on Linux, not on a CI and Xvfb is available.

    This is a lot nicer than having windows popping up.
    """
    config.xvfb_display = None
    if os.environ.get('DISPLAY', None) == '':
        # xvfbwrapper doesn't handle DISPLAY="" correctly
        del os.environ['DISPLAY']

    if (sys.platform.startswith('linux') and
            not config.getoption('--no-xvfb') and
            'QUTE_NO_DISPLAY' not in os.environ):
        assert 'QUTE_BUILDBOT' not in os.environ
        try:
            disp = xvfbwrapper.Xvfb(width=800, height=600, colordepth=16)
            disp.start()
        except FileNotFoundError:
            # We run without Xvfb if it's unavailable.
            pass
        else:
            config.xvfb_display = disp


def pytest_unconfigure(config):
    if config.xvfb_display is not None:
        config.xvfb_display.stop()
