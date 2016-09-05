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
import warnings

import pytest
import hypothesis

pytest.register_assert_rewrite('helpers')

from helpers import logfail
from helpers.logfail import fail_on_logging
from helpers.messagemock import message_mock
from helpers.fixtures import *  # pylint: disable=wildcard-import


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
        ('ci', 'CI' not in os.environ, "Only runs on CI."),
    ]

    for searched_marker, condition, default_reason in markers:
        marker = item.get_marker(searched_marker)
        if not marker or not condition:
            continue

        if 'reason' in marker.kwargs:
            reason = '{}: {}'.format(default_reason, marker.kwargs['reason'])
            del marker.kwargs['reason']
        else:
            reason = default_reason + '.'
        skipif_marker = pytest.mark.skipif(condition, *marker.args,
                                           reason=reason, **marker.kwargs)
        item.add_marker(skipif_marker)


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
        http://pytest.org/latest/plugins.html
    """
    remaining_items = []
    deselected_items = []

    for item in items:
        deselected = False

        if 'qapp' in getattr(item, 'fixturenames', ()):
            item.add_marker('gui')

        if hasattr(item, 'module'):
            module_path = os.path.relpath(
                item.module.__file__,
                os.path.commonprefix([__file__, item.module.__file__]))

            module_root_dir = module_path.split(os.sep)[0]
            assert module_root_dir in ['end2end', 'unit', 'helpers',
                                       'test_conftest.py']
            if module_root_dir == 'end2end':
                item.add_marker(pytest.mark.end2end)
            elif os.environ.get('QUTE_BDD_WEBENGINE', ''):
                deselected = True

        _apply_platform_markers(item)
        if item.get_marker('xfail_norun'):
            item.add_marker(pytest.mark.xfail(run=False))
        if item.get_marker('flaky_once'):
            item.add_marker(pytest.mark.flaky(reruns=1))

        if deselected:
            deselected_items.append(item)
        else:
            remaining_items.append(item)

    config.hook.pytest_deselected(items=deselected_items)
    items[:] = remaining_items


def pytest_ignore_collect(path):
    """Ignore BDD tests if we're unable to run them."""
    skip_bdd = hasattr(sys, 'frozen')
    rel_path = path.relto(os.path.dirname(__file__))
    return rel_path == os.path.join('end2end', 'features') and skip_bdd


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
    webengine_env = os.environ.get('QUTE_BDD_WEBENGINE', '')
    config.webengine = bool(webengine_arg or webengine_env)
    # Fail early if QtWebEngine is not available
    # pylint: disable=no-name-in-module,unused-variable,useless-suppression
    if config.webengine:
        import PyQt5.QtWebEngineWidgets
    # pylint: enable=no-name-in-module,unused-variable,useless-suppression


@pytest.fixture(scope='session', autouse=True)
def check_display(request):
    if (not request.config.getoption('--no-xvfb') and
            'QUTE_BUILDBOT' in os.environ and
            request.config.xvfb is not None):
        raise Exception("Xvfb is running on buildbot!")

    if sys.platform == 'linux' and not os.environ.get('DISPLAY', ''):
        raise Exception("No display and no Xvfb available!")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Make test information available in fixtures.

    See http://pytest.org/latest/example/simple.html#making-test-result-information-available-in-fixtures
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(exitstatus):
    """Create a file to tell run_pytest.py how pytest exited."""
    outcome = yield
    outcome.get_result()

    cache_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             '..', '.cache')
    try:
        os.mkdir(cache_dir)
    except FileExistsError:
        pass

    status_file = os.path.join(cache_dir, 'pytest_status')
    with open(status_file, 'w', encoding='ascii') as f:
        f.write(str(exitstatus))
