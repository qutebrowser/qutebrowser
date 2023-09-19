# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
