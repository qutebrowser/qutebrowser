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


import logging

import pytest
import pytest_capturelog  # pylint: disable=import-error


def test_log_debug():
    logging.debug('foo')


def test_log_warning():
    with pytest.raises(pytest.fail.Exception):
        logging.warning('foo')


def test_log_expected(caplog):
    with caplog.atLevel(logging.ERROR):
        logging.error('foo')


def test_log_expected_logger(caplog):
    logger = 'logfail_test_logger'
    with caplog.atLevel(logging.ERROR, logger):
        logging.getLogger(logger).error('foo')


def test_log_expected_wrong_level(caplog):
    with pytest.raises(pytest.fail.Exception):
        with caplog.atLevel(logging.ERROR):
            logging.critical('foo')


def test_log_expected_logger_wrong_level(caplog):
    logger = 'logfail_test_logger'
    with pytest.raises(pytest.fail.Exception):
        with caplog.atLevel(logging.ERROR, logger):
            logging.getLogger(logger).critical('foo')


def test_log_expected_wrong_logger(caplog):
    logger = 'logfail_test_logger'
    with pytest.raises(pytest.fail.Exception):
        with caplog.atLevel(logging.ERROR, logger):
            logging.error('foo')


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
