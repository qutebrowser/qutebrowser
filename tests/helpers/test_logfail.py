# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for the LogFailHandler test helper."""


import os.path
import logging

import pytest
import pytest_capturelog  # pylint: disable=import-error


pytest_plugins = 'pytester'




@pytest.fixture
def log_testdir(testdir):
    """Testdir which uses our logfail.py as a conftest."""
    log_fn = os.path.join(os.path.dirname(__file__), 'logfail.py')
    with open(log_fn) as f:
        testdir.makeconftest(f.read())
    return testdir


def test_log_debug(log_testdir):
    log_testdir.makepyfile("""
        import logging

        def test_foo():
            logging.debug('foo')
    """)
    res = log_testdir.runpytest('-p capturelog')
    res.stdout.fnmatch_lines(['*1 passed*'])


def test_log_warning(log_testdir):
    log_testdir.makepyfile("""
        import logging

        def test_foo():
            logging.warning('foo')
    """)
    res = log_testdir.runpytest('-p capturelog')
    res.stdout.fnmatch_lines(['*1 error*'])


def test_log_expected(log_testdir):
    """For some reason this fails with inline_run."""
    log_testdir.makepyfile("""
        import logging

        def test_foo(caplog):
            with caplog.atLevel(logging.ERROR):
                logging.error('foo')
    """)
    res = log_testdir.runpytest('-p capturelog')
    res.stdout.fnmatch_lines(['*1 passed*'])


def test_log_expected_logger(log_testdir):
    log_testdir.makepyfile("""
        import logging

        def test_foo(caplog):
            logger = 'logfail_test_logger'
            with caplog.atLevel(logging.ERROR, logger):
                logging.getLogger(logger).error('foo')
    """)
    res = log_testdir.runpytest('-p capturelog')
    res.stdout.fnmatch_lines(['*1 passed*'])


def test_log_expected_wrong_level(log_testdir):
    log_testdir.makepyfile("""
        import logging

        def test_foo(caplog):
            with caplog.atLevel(logging.ERROR):
                logging.critical('foo')
    """)
    res = log_testdir.runpytest('-p capturelog')
    res.stdout.fnmatch_lines(['*1 error*'])


def test_log_expected_logger_wrong_level(log_testdir):
    log_testdir.makepyfile("""
        import logging

        def test_foo(caplog):
            logger = 'logfail_test_logger'
            with caplog.atLevel(logging.ERROR, logger):
                logging.getLogger(logger).critical('foo')
    """)
    res = log_testdir.runpytest('-p capturelog')
    res.stdout.fnmatch_lines(['*1 error*'])


def test_log_expected_wrong_logger(log_testdir):
    log_testdir.makepyfile("""
        import logging

        def test_foo(caplog):
            logger = 'logfail_test_logger'
            with caplog.atLevel(logging.ERROR, logger):
                logging.error('foo')
    """)
    res = log_testdir.runpytest('-p capturelog')
    res.stdout.fnmatch_lines(['*1 error*'])


@pytest.fixture
def skipping_fixture():
    pytest.skip("Skipping to test caplog workaround.")


def test_caplog_bug_workaround_1(caplog, skipping_fixture):
    pass


def test_caplog_bug_workaround_2():
    """Make sure caplog_bug_workaround works correctly after a skipped test.

    There should be only one capturelog handler.
    """
    caplog_handler = None
    for h in logging.getLogger().handlers:
        if isinstance(h, pytest_capturelog.CaptureLogHandler):
            assert caplog_handler is None
            caplog_handler = h
