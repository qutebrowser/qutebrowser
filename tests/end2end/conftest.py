# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=unused-import

"""Things needed for end2end testing."""

import re
import os
import pathlib
import sys
import shutil
import pstats
import operator

import pytest
from PyQt5.QtCore import PYQT_VERSION, QCoreApplication

pytest.register_assert_rewrite('end2end.fixtures')

from end2end.fixtures.notificationserver import notification_server
from end2end.fixtures.webserver import server, server_per_test, server2, ssl_server
from end2end.fixtures.quteprocess import (quteproc_process, quteproc,
                                          quteproc_new)
from end2end.fixtures.testprocess import pytest_runtest_makereport
from qutebrowser.utils import qtutils, utils
from qutebrowser.browser.webengine import spell


def pytest_configure(config):
    """Remove old profile files."""
    if config.getoption('--qute-profile-subprocs'):
        try:
            shutil.rmtree('prof')
        except FileNotFoundError:
            pass


def pytest_unconfigure(config):
    """Combine profiles."""
    if config.getoption('--qute-profile-subprocs'):
        stats = pstats.Stats()
        for fn in pathlib.Path('prof').iterdir():
            stats.add((pathlib.Path('prof') / fn))
        stats.dump_stats((pathlib.Path('prof') / 'combined.pstats'))


def _check_hex_version(op_str, running_version, version):
    operators = {
        '==': operator.eq,
        '!=': operator.ne,
        '>=': operator.ge,
        '<=': operator.le,
        '>': operator.gt,
        '<': operator.lt,
    }
    op = operators[op_str]
    major, minor, patch = [int(e) for e in version.split('.')]
    hex_version = (major << 16) | (minor << 8) | patch
    return op(running_version, hex_version)


def _get_version_tag(tag):
    """Handle tags like pyqt>=5.3.1 for BDD tests.

    This transforms e.g. pyqt>=5.3.1 into an appropriate @pytest.mark.skip
    marker, and falls back to pytest-bdd's implementation for all other
    casesinto an appropriate @pytest.mark.skip marker, and falls back to
    """
    version_re = re.compile(r"""
        (?P<package>qt|pyqt|pyqtwebengine)
        (?P<operator>==|>=|!=|<)
        (?P<version>\d+\.\d+(\.\d+)?)
    """, re.VERBOSE)

    match = version_re.fullmatch(tag)
    if not match:
        return None

    package = match.group('package')
    version = match.group('version')

    if package == 'qt':
        op = match.group('operator')
        do_skip = {
            '==': not qtutils.version_check(version, exact=True,
                                            compiled=False),
            '>=': not qtutils.version_check(version, compiled=False),
            '<': qtutils.version_check(version, compiled=False),
            '!=': qtutils.version_check(version, exact=True, compiled=False),
        }
        return pytest.mark.skipif(do_skip[op], reason='Needs ' + tag)
    elif package == 'pyqt':
        return pytest.mark.skipif(
            not _check_hex_version(
                op_str=match.group('operator'),
                running_version=PYQT_VERSION,
                version=version
            ),
            reason='Needs ' + tag,
        )
    elif package == 'pyqtwebengine':
        try:
            from PyQt5.QtWebEngine import PYQT_WEBENGINE_VERSION
        except ImportError:
            running_version = PYQT_VERSION
        else:
            running_version = PYQT_WEBENGINE_VERSION
        return pytest.mark.skipif(
            not _check_hex_version(
                op_str=match.group('operator'),
                running_version=running_version,
                version=version
            ),
            reason='Needs ' + tag,
        )
    else:
        raise utils.Unreachable(package)


def _get_backend_tag(tag):
    """Handle a @qtwebengine_*/@qtwebkit_skip tag."""
    pytest_marks = {
        'qtwebengine_todo': pytest.mark.qtwebengine_todo,
        'qtwebengine_skip': pytest.mark.qtwebengine_skip,
        'qtwebengine_notifications': pytest.mark.qtwebengine_notifications,
        'qtwebkit_skip': pytest.mark.qtwebkit_skip,
    }
    if not any(tag.startswith(t + ':') for t in pytest_marks):
        return None
    name, desc = tag.split(':', maxsplit=1)
    return pytest_marks[name](desc)


if not getattr(sys, 'frozen', False):
    def pytest_bdd_apply_tag(tag, function):
        """Handle custom tags for BDD tests.

        This tries various functions, and if none knows how to handle this tag,
        it returns None so it falls back to pytest-bdd's implementation.
        """
        funcs = [_get_version_tag, _get_backend_tag]
        for func in funcs:
            mark = func(tag)
            if mark is not None:
                mark(function)
                return True
        return None


def pytest_collection_modifyitems(config, items):
    """Apply @qtwebengine_* markers; skip unittests with QUTE_BDD_WEBENGINE."""
    # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-75884
    # (note this isn't actually fixed properly before Qt 5.15)
    header_bug_fixed = qtutils.version_check('5.15', compiled=False)

    lib_path = pathlib.Path(QCoreApplication.libraryPaths()[0])
    qpdf_image_plugin = lib_path / 'imageformats' / 'libqpdf.so'

    markers = [
        ('qtwebengine_todo', 'QtWebEngine TODO', pytest.mark.xfail,
         config.webengine),
        ('qtwebengine_skip', 'Skipped with QtWebEngine', pytest.mark.skipif,
         config.webengine),
        ('qtwebengine_notifications',
         'Skipped unless QtWebEngine >= 5.13',
         pytest.mark.skipif,
         not (config.webengine and qtutils.version_check('5.13'))),
        ('qtwebkit_skip', 'Skipped with QtWebKit', pytest.mark.skipif,
         not config.webengine),
        ('qtwebengine_flaky', 'Flaky with QtWebEngine', pytest.mark.skipif,
         config.webengine),
        ('qtwebengine_mac_xfail', 'Fails on macOS with QtWebEngine',
         pytest.mark.xfail, config.webengine and utils.is_mac),
        ('js_headers', 'Sets headers dynamically via JS',
         pytest.mark.skipif,
         config.webengine and not header_bug_fixed),
        ('qtwebkit_pdf_imageformat_skip',
         'Skipped with QtWebKit if PDF image plugin is available',
         pytest.mark.skipif,
         not config.webengine and qpdf_image_plugin.exists()),
        ('windows_skip',
         'Skipped on Windows',
         pytest.mark.skipif,
         utils.is_windows),
    ]

    for item in items:
        for name, prefix, pytest_mark, condition in markers:
            marker = item.get_closest_marker(name)
            if marker and condition:
                if marker.args:
                    text = '{}: {}'.format(prefix, marker.args[0])
                else:
                    text = prefix
                item.add_marker(pytest_mark(condition, reason=text,
                                            **marker.kwargs))
