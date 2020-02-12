# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


def test_log_debug():
    logging.debug('foo')


def test_log_warning():
    with pytest.raises(pytest.fail.Exception):
        logging.warning('foo')


def test_log_expected(caplog):
    with caplog.at_level(logging.ERROR):
        logging.error('foo')


def test_log_expected_logger(caplog):
    logger = 'logfail_test_logger'
    with caplog.at_level(logging.ERROR, logger):
        logging.getLogger(logger).error('foo')


def test_log_expected_wrong_level(caplog):
    with pytest.raises(pytest.fail.Exception):
        with caplog.at_level(logging.ERROR):
            logging.critical('foo')


def test_log_expected_logger_wrong_level(caplog):
    logger = 'logfail_test_logger'
    with pytest.raises(pytest.fail.Exception):
        with caplog.at_level(logging.ERROR, logger):
            logging.getLogger(logger).critical('foo')


def test_log_expected_wrong_logger(caplog):
    logger = 'logfail_test_logger'
    with pytest.raises(pytest.fail.Exception):
        with caplog.at_level(logging.ERROR, logger):
            logging.error('foo')
