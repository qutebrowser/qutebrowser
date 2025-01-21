# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Things needed for end2end testing."""

import re
import pathlib
import sys
import shutil
import pstats
import operator

import pytest
from qutebrowser.qt.core import PYQT_VERSION, QCoreApplication

pytest.register_assert_rewrite('end2end.fixtures')

# pylint: disable=unused-import
# Import fixtures that the bdd tests rely on.
from end2end.fixtures.notificationserver import notification_server
from end2end.fixtures.webserver import server, server_per_test, server2, ssl_server
from end2end.fixtures.quteprocess import (
    quteproc_process, quteproc,
    quteproc_new,
    screenshot_dir,
    take_x11_screenshot,
)
from end2end.fixtures.testprocess import pytest_runtest_makereport
# pylint: enable=unused-import
from qutebrowser.utils import qtutils, utils


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
            stats.add(pathlib.Path('prof') / fn)
        stats.dump_stats(pathlib.Path('prof') / 'combined.pstats')


def _check_version(op_str, running_version, version_str, as_hex=False):
    operators = {
        '==': operator.eq,
        '!=': operator.ne,
        '>=': operator.ge,
        '<=': operator.le,
        '>': operator.gt,
        '<': operator.lt,
    }
    op = operators[op_str]
    major, minor, patch = (int(e) for e in version_str.split('.'))
    if as_hex:
        version = (major << 16) | (minor << 8) | patch
    else:
        version = (major, minor, patch)
    return op(running_version, version)


def _get_version_tag(tag):
    """Handle tags like pyqt>=5.3.1 for BDD tests.

    This transforms e.g. pyqt>=5.3.1 into an appropriate @pytest.mark.skip
    marker, and falls back to pytest-bdd's implementation for all other
    casesinto an appropriate @pytest.mark.skip marker, and falls back to
    """
    version_re = re.compile(r"""
        (?P<package>qt|pyqt|pyqtwebengine|python)
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
            not _check_version(
                op_str=match.group('operator'),
                running_version=PYQT_VERSION,
                version_str=version,
                as_hex=True,
            ),
            reason='Needs ' + tag,
        )
    elif package == 'pyqtwebengine':
        try:
            from qutebrowser.qt.webenginecore import PYQT_WEBENGINE_VERSION
        except ImportError:
            # QtWebKit
            running_version = PYQT_VERSION
        else:
            running_version = PYQT_WEBENGINE_VERSION
        return pytest.mark.skipif(
            not _check_version(
                op_str=match.group('operator'),
                running_version=running_version,
                version_str=version,
                as_hex=True,
            ),
            reason='Needs ' + tag,
        )
    elif package == 'python':
        running_version = sys.version_info
        return pytest.mark.skipif(
            not _check_version(
                op_str=match.group('operator'),
                running_version=running_version,
                version_str=version,
            ),
            reason='Needs ' + tag,
        )
    else:
        raise utils.Unreachable(package)


if not getattr(sys, 'frozen', False):
    def pytest_bdd_apply_tag(tag, function):
        """Handle custom tags for BDD tests.

        If we return None, this falls back to pytest-bdd's implementation.
        """
        mark = _get_version_tag(tag)
        if mark is not None:
            mark(function)
            return True
        return None


def pytest_collection_modifyitems(config, items):
    """Apply @qtwebengine_* markers."""
    lib_path = pathlib.Path(QCoreApplication.libraryPaths()[0])
    qpdf_image_plugin = lib_path / 'imageformats' / 'libqpdf.so'

    markers = [
        ('qtwebengine_todo', 'QtWebEngine TODO', pytest.mark.xfail,
         config.webengine),
        ('qtwebengine_skip', 'Skipped with QtWebEngine', pytest.mark.skipif,
         config.webengine),
        ('qtwebkit_skip', 'Skipped with QtWebKit', pytest.mark.skipif,
         not config.webengine),
        ('qtwebengine_flaky', 'Flaky with QtWebEngine', pytest.mark.skipif,
         config.webengine),
        ('qtwebengine_mac_xfail', 'Fails on macOS with QtWebEngine',
         pytest.mark.xfail, config.webengine and utils.is_mac),
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
