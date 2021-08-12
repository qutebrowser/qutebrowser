# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

# pylint: disable=unused-import,wildcard-import,unused-wildcard-import

"""The qutebrowser test suite conftest file."""

import os
import pathlib
import sys
import warnings

import pytest
import hypothesis
from PyQt5.QtCore import PYQT_VERSION

pytest.register_assert_rewrite('helpers')

from helpers import logfail
from helpers.logfail import fail_on_logging
from helpers.messagemock import message_mock
from helpers.fixtures import *  # noqa: F403
from helpers import testutils
from qutebrowser.utils import qtutils, standarddir, usertypes, utils, version
from qutebrowser.misc import objects, earlyinit
from qutebrowser.qt import sip

import qutebrowser.app  # To register commands


_qute_scheme_handler = None


# Set hypothesis settings
hypothesis.settings.register_profile(
    'default', hypothesis.settings(
        deadline=600,
        suppress_health_check=[hypothesis.HealthCheck.function_scoped_fixture],
    )
)
hypothesis.settings.register_profile(
    'ci', hypothesis.settings(
        deadline=None,
        suppress_health_check=[
            hypothesis.HealthCheck.function_scoped_fixture,
            hypothesis.HealthCheck.too_slow,
        ]
    )
)
hypothesis.settings.load_profile('ci' if testutils.ON_CI else 'default')


def _apply_platform_markers(config, item):
    """Apply a skip marker to a given item."""
    markers = [
        ('posix',
         pytest.mark.skipif,
         not utils.is_posix,
         "Requires a POSIX os"),
        ('windows',
         pytest.mark.skipif,
         not utils.is_windows,
         "Requires Windows"),
        ('linux',
         pytest.mark.skipif,
         not utils.is_linux,
         "Requires Linux"),
        ('mac',
         pytest.mark.skipif,
         not utils.is_mac,
         "Requires macOS"),
        ('not_mac',
         pytest.mark.skipif,
         utils.is_mac,
         "Skipped on macOS"),
        ('not_frozen',
         pytest.mark.skipif,
         getattr(sys, 'frozen', False),
         "Can't be run when frozen"),
        ('not_flatpak',
         pytest.mark.skipif,
         version.is_flatpak(),
         "Can't be run with Flatpak"),
        ('frozen',
         pytest.mark.skipif,
         not getattr(sys, 'frozen', False),
         "Can only run when frozen"),
        ('ci',
         pytest.mark.skipif,
         not testutils.ON_CI,
         "Only runs on CI."),
        ('no_ci',
         pytest.mark.skipif,
         testutils.ON_CI,
         "Skipped on CI."),
        ('unicode_locale',
         pytest.mark.skipif,
         sys.getfilesystemencoding() == 'ascii',
         "Skipped because of ASCII locale"),
    ]

    for searched_marker, new_marker_kind, condition, default_reason in markers:
        marker = item.get_closest_marker(searched_marker)
        if not marker or not condition:
            continue

        if 'reason' in marker.kwargs:
            reason = '{}: {}'.format(default_reason, marker.kwargs['reason'])
            del marker.kwargs['reason']
        else:
            reason = default_reason + '.'
        new_marker = new_marker_kind(condition, *marker.args,
                                     reason=reason, **marker.kwargs)
        item.add_marker(new_marker)


def pytest_collection_modifyitems(config, items):
    """Handle custom markers.

    pytest hook called after collection has been performed.

    Adds a marker named "gui" which can be used to filter gui tests from the
    command line.

    For example:

        pytest -m "not gui"  # run all tests except gui tests
        pytest -m "gui"  # run only gui tests

    It also handles the platform specific markers by translating them to skipif
    markers.

    Args:
        items: list of _pytest.main.Node items, where each item represents
               a python test that will be executed.

    Reference:
        https://pytest.org/latest/plugins.html
    """
    remaining_items = []
    deselected_items = []

    for item in items:
        deselected = False

        if 'qapp' in getattr(item, 'fixturenames', ()):
            item.add_marker('gui')

        if hasattr(item, 'module'):
            test_basedir = pathlib.Path(__file__).parent
            module_path = pathlib.Path(item.module.__file__)
            module_root_dir = module_path.relative_to(test_basedir).parts[0]

            assert module_root_dir in ['end2end', 'unit', 'helpers',
                                       'test_conftest.py']
            if module_root_dir == 'end2end':
                item.add_marker(pytest.mark.end2end)

        _apply_platform_markers(config, item)
        if list(item.iter_markers('xfail_norun')):
            item.add_marker(pytest.mark.xfail(run=False))

        if deselected:
            deselected_items.append(item)
        else:
            remaining_items.append(item)

    config.hook.pytest_deselected(items=deselected_items)
    items[:] = remaining_items


def pytest_ignore_collect(path):
    """Ignore BDD tests if we're unable to run them."""
    fspath = pathlib.Path(path)
    skip_bdd = hasattr(sys, 'frozen')
    rel_path = fspath.relative_to(pathlib.Path(__file__).parent)
    return rel_path == pathlib.Path('end2end') / 'features' and skip_bdd


@pytest.fixture(scope='session')
def qapp_args():
    """Make QtWebEngine unit tests run on older Qt versions + newer kernels."""
    seccomp_args = testutils.seccomp_args(qt_flag=False)
    if seccomp_args:
        return [sys.argv[0]] + seccomp_args
    return []


@pytest.fixture(scope='session')
def qapp(qapp):
    """Change the name of the QApplication instance."""
    qapp.setApplicationName('qute_test')
    return qapp


def pytest_addoption(parser):
    parser.addoption('--qute-delay', action='store', default=0, type=int,
                     help="Delay between qutebrowser commands.")
    parser.addoption('--qute-profile-subprocs', action='store_true',
                     default=False, help="Run cProfile for subprocesses.")
    parser.addoption('--qute-bdd-webengine', action='store_true',
                     help='Use QtWebEngine for BDD tests')


def pytest_configure(config):
    webengine_arg = config.getoption('--qute-bdd-webengine')
    webengine_env = os.environ.get('QUTE_BDD_WEBENGINE', 'false')
    config.webengine = webengine_arg or webengine_env == 'true'
    # Fail early if QtWebEngine is not available
    if config.webengine:
        import PyQt5.QtWebEngineWidgets
    earlyinit.configure_pyqt()


@pytest.fixture(scope='session', autouse=True)
def check_display(request):
    if utils.is_linux and not os.environ.get('DISPLAY', ''):
        raise Exception("No display and no Xvfb available!")


@pytest.fixture(autouse=True)
def set_backend(monkeypatch, request):
    """Make sure the backend global is set."""
    if not request.config.webengine and version.qWebKitVersion:
        backend = usertypes.Backend.QtWebKit
    else:
        backend = usertypes.Backend.QtWebEngine
    monkeypatch.setattr(objects, 'backend', backend)


@pytest.fixture(autouse=True)
def apply_fake_os(monkeypatch, request):
    fake_os = request.node.get_closest_marker('fake_os')
    if not fake_os:
        return

    name = fake_os.args[0]
    mac = False
    windows = False
    linux = False
    posix = False

    if name == 'unknown':
        pass
    elif name == 'mac':
        mac = True
        posix = True
    elif name == 'windows':
        windows = True
    elif name == 'linux':
        linux = True
        posix = True
    elif name == 'posix':
        posix = True
    else:
        raise ValueError("Invalid fake_os {}".format(name))

    monkeypatch.setattr(utils, 'is_mac', mac)
    monkeypatch.setattr(utils, 'is_linux', linux)
    monkeypatch.setattr(utils, 'is_windows', windows)
    monkeypatch.setattr(utils, 'is_posix', posix)


@pytest.fixture(scope='session', autouse=True)
def check_yaml_c_exts():
    """Make sure PyYAML C extensions are available on CI.

    Not available yet with a nightly Python, see:
    https://github.com/yaml/pyyaml/issues/416
    """
    if testutils.ON_CI and sys.version_info[:2] != (3, 10):
        from yaml import CLoader


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Make test information available in fixtures.

    See https://pytest.org/latest/example/simple.html#making-test-result-information-available-in-fixtures
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.hookimpl(hookwrapper=True)
def pytest_terminal_summary(terminalreporter):
    """Group benchmark results on CI."""
    if testutils.ON_CI:
        terminalreporter.write_line(
            testutils.gha_group_begin('Benchmark results'))
        yield
        terminalreporter.write_line(testutils.gha_group_end())
    else:
        yield
