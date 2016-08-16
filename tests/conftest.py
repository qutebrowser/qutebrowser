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

import re
import os
import sys
import warnings
import operator

import pytest
import hypothesis

from helpers import logfail
from helpers.logfail import fail_on_logging
from helpers.messagemock import message_mock
from helpers.fixtures import *  # pylint: disable=wildcard-import

from PyQt5.QtCore import PYQT_VERSION

from qutebrowser.utils import qtutils


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

        if hasattr(item, 'module'):
            module_path = os.path.relpath(
                item.module.__file__,
                os.path.commonprefix([__file__, item.module.__file__]))

            module_root_dir = os.path.split(module_path)[0]
            if module_root_dir == 'end2end':
                item.add_marker(pytest.mark.end2end)

        _apply_platform_markers(item)
        if item.get_marker('xfail_norun'):
            item.add_marker(pytest.mark.xfail(run=False))
        if item.get_marker('flaky_once'):
            item.add_marker(pytest.mark.flaky(reruns=1))


def pytest_ignore_collect(path):
    """Ignore BDD tests if we're unable to run them."""
    skip_bdd = (hasattr(sys, 'frozen') or
                int(pytest.__version__.split('.')[0]) == 3)
    skip_bdd = True
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


if not getattr(sys, 'frozen', False):
    def pytest_bdd_apply_tag(tag, function):
        """Handle tags like pyqt>=5.3.1 for BDD tests.

        This transforms e.g. pyqt>=5.3.1 into an appropriate @pytest.mark.skip
        marker, and falls back to pytest-bdd's implementation for all other
        casesinto an appropriate @pytest.mark.skip marker, and falls back to
        pytest-bdd's implementation for all other cases
        """
        version_re = re.compile(r"""
            (?P<package>qt|pyqt)
            (?P<operator>==|>|>=|<|<=|!=)
            (?P<version>\d+\.\d+\.\d+)
        """, re.VERBOSE)

        match = version_re.match(tag)
        if not match:
            # Use normal tag mapping
            return None

        operators = {
            '==': operator.eq,
            '>': operator.gt,
            '<': operator.lt,
            '>=': operator.ge,
            '<=': operator.le,
            '!=': operator.ne,
        }

        package = match.group('package')
        op = operators[match.group('operator')]
        version = match.group('version')

        if package == 'qt':
            mark = pytest.mark.skipif(qtutils.version_check(version, op),
                                      reason='Needs ' + tag)
        elif package == 'pyqt':
            major, minor, patch = [int(e) for e in version.split('.')]
            hex_version = (major << 16) | (minor << 8) | patch
            mark = pytest.mark.skipif(not op(PYQT_VERSION, hex_version),
                                      reason='Needs ' + tag)
        else:
            raise ValueError("Invalid package {!r}".format(package))

        mark(function)
        return True
