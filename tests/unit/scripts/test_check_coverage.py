#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import sys

import pytest

from scripts.dev import check_coverage


pytest_plugins = 'pytester'
pytestmark = [pytest.mark.linux, pytest.mark.not_frozen]


class CovtestHelper:

    """Helper object for covtest fixture.

    Attributes:
        _testdir: The testdir fixture from pytest.
        _monkeypatch: The monkeypatch fixture from pytest.
    """

    def __init__(self, testdir, monkeypatch):
        self._testdir = testdir
        self._monkeypatch = monkeypatch

    def makefile(self, code):
        """Generate a module.py for the given code."""
        self._testdir.makepyfile(module=code)

    def run(self):
        """Run pytest with coverage for the given module.py."""
        coveragerc = str(self._testdir.tmpdir / 'coveragerc')
        return self._testdir.runpytest('--cov=module',
                                       '--cov-config={}'.format(coveragerc),
                                       '--cov-report=xml',
                                       plugins=['no:faulthandler'])

    def check(self, perfect_files=None):
        """Run check_coverage.py and run its return value."""
        coverage_file = self._testdir.tmpdir / 'coverage.xml'

        if perfect_files is None:
            perfect_files = [(None, 'module.py')]

        argv = [sys.argv[0]]
        self._monkeypatch.setattr('scripts.dev.check_coverage.sys.argv', argv)

        with self._testdir.tmpdir.as_cwd():
            with coverage_file.open(encoding='utf-8') as f:
                return check_coverage.check(f, perfect_files=perfect_files)

    def check_skipped(self, args, reason):
        """Run check_coverage.py and make sure it's skipped."""
        argv = [sys.argv[0]] + list(args)
        self._monkeypatch.setattr('scripts.dev.check_coverage.sys.argv', argv)
        with pytest.raises(check_coverage.Skipped) as excinfo:
            return check_coverage.check(None, perfect_files=[])
        assert excinfo.value.reason == reason


@pytest.fixture
def covtest(testdir, monkeypatch):
    """Fixture which provides a coveragerc and a test to call module.func."""
    testdir.makefile(ext='', coveragerc="""
        [run]
        branch=True
    """)
    testdir.makepyfile(test_module="""
        from module import func

        def test_module():
            func()
    """)
    return CovtestHelper(testdir, monkeypatch)


def test_tested_no_branches(covtest):
    covtest.makefile("""
        def func():
            pass
    """)
    covtest.run()
    assert covtest.check() == []


def test_tested_with_branches(covtest):
    covtest.makefile("""
        def func2(arg):
            if arg:
                pass
            else:
                pass

        def func():
            func2(True)
            func2(False)
    """)
    covtest.run()
    assert covtest.check() == []


def test_untested(covtest):
    covtest.makefile("""
        def func():
            pass

        def untested():
            pass
    """)
    covtest.run()
    expected = check_coverage.Message(
        check_coverage.MsgType.insufficent_coverage,
        'module.py has 75.0% line and 100.0% branch coverage!')
    assert covtest.check() == [expected]


def test_untested_branches(covtest):
    covtest.makefile("""
        def func2(arg):
            if arg:
                pass
            else:
                pass

        def func():
            func2(True)
    """)
    covtest.run()
    expected = check_coverage.Message(
        check_coverage.MsgType.insufficent_coverage,
        'module.py has 100.0% line and 50.0% branch coverage!')
    assert covtest.check() == [expected]


def test_tested_unlisted(covtest):
    covtest.makefile("""
        def func():
            pass
    """)
    covtest.run()
    expected = check_coverage.Message(
        check_coverage.MsgType.perfect_file,
        'module.py has 100% coverage but is not in perfect_files!')
    assert covtest.check(perfect_files=[]) == [expected]


@pytest.mark.parametrize('args, reason', [
    (['-k', 'foo'], "because -k is given."),
    (['-m', 'foo'], "because -m is given."),
    (['--lf'], "because --lf is given."),
    (['blah', '-m', 'foo'], "because -m is given."),
    (['tests/foo'], "because there is nothing to check."),
])
def test_skipped_args(covtest, args, reason):
    covtest.check_skipped(args, reason)


def test_skipped_windows(covtest, monkeypatch):
    monkeypatch.setattr('scripts.dev.check_coverage.sys.platform', 'toaster')
    covtest.check_skipped([], "on non-Linux system.")
