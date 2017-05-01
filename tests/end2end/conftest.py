# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Things needed for end2end testing."""

import re
import os
import sys
import shutil
import pstats
import os.path
import operator

import pytest
from PyQt5.QtCore import PYQT_VERSION

pytest.register_assert_rewrite('end2end.fixtures')

from end2end.fixtures.webserver import httpbin, httpbin_after_test, ssl_server
from end2end.fixtures.quteprocess import (quteproc_process, quteproc,
                                          quteproc_new)
from end2end.fixtures.testprocess import pytest_runtest_makereport
from qutebrowser.utils import qtutils


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
        for fn in os.listdir('prof'):
            stats.add(os.path.join('prof', fn))
        stats.dump_stats(os.path.join('prof', 'combined.pstats'))


def _get_version_tag(tag):
    """Handle tags like pyqt>=5.3.1 for BDD tests.

    This transforms e.g. pyqt>=5.3.1 into an appropriate @pytest.mark.skip
    marker, and falls back to pytest-bdd's implementation for all other
    casesinto an appropriate @pytest.mark.skip marker, and falls back to
    """
    version_re = re.compile(r"""
        (?P<package>qt|pyqt)
        (?P<operator>==|>=|!=|<)
        (?P<version>\d+\.\d+(\.\d+)?)
    """, re.VERBOSE)

    match = version_re.match(tag)
    if not match:
        return None

    package = match.group('package')
    version = match.group('version')

    if package == 'qt':
        op = match.group('operator')
        do_skip = {
            '==': not qtutils.version_check(version, exact=True),
            '>=': not qtutils.version_check(version),
            '<': qtutils.version_check(version),
            '!=': qtutils.version_check(version, exact=True),
        }
        return pytest.mark.skipif(do_skip[op], reason='Needs ' + tag)
    elif package == 'pyqt':
        operators = {
            '==': operator.eq,
            '>=': operator.ge,
            '!=': operator.ne,
        }
        op = operators[match.group('operator')]
        major, minor, patch = [int(e) for e in version.split('.')]
        hex_version = (major << 16) | (minor << 8) | patch
        return pytest.mark.skipif(not op(PYQT_VERSION, hex_version),
                                  reason='Needs ' + tag)
    else:
        raise ValueError("Invalid package {!r}".format(package))


def _get_backend_tag(tag):
    """Handle a @qtwebengine_*/@qtwebkit_skip tag."""
    pytest_marks = {
        'qtwebengine_todo': pytest.mark.qtwebengine_todo,
        'qtwebengine_skip': pytest.mark.qtwebengine_skip,
        'qtwebkit_skip': pytest.mark.qtwebkit_skip,
        'qtwebkit_ng_xfail': pytest.mark.qtwebkit_ng_xfail,
        'qtwebkit_ng_skip': pytest.mark.qtwebkit_ng_skip,
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
    markers = [
        ('qtwebengine_todo', 'QtWebEngine TODO', pytest.mark.xfail,
         config.webengine),
        ('qtwebengine_skip', 'Skipped with QtWebEngine', pytest.mark.skipif,
         config.webengine),
        ('qtwebkit_skip', 'Skipped with QtWebKit', pytest.mark.skipif,
         not config.webengine),
        ('qtwebkit_ng_xfail', 'Failing with QtWebKit-NG', pytest.mark.xfail,
         not config.webengine and qtutils.is_qtwebkit_ng()),
        ('qtwebkit_ng_skip', 'Skipped with QtWebKit-NG', pytest.mark.skipif,
         not config.webengine and qtutils.is_qtwebkit_ng()),
        ('qtwebengine_flaky', 'Flaky with QtWebEngine', pytest.mark.skipif,
         config.webengine),
        ('qtwebengine_osx_xfail', 'Fails on OS X with QtWebEngine',
         pytest.mark.xfail, config.webengine and sys.platform == 'darwin'),
    ]

    for item in items:
        for name, prefix, pytest_mark, condition in markers:
            marker = item.get_marker(name)
            if marker and condition:
                if marker.args:
                    text = '{}: {}'.format(prefix, marker.args[0])
                else:
                    text = prefix
                item.add_marker(pytest_mark(condition, reason=text,
                                            **marker.kwargs))
