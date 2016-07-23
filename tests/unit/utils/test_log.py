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

"""Tests for qutebrowser.utils.log."""

import logging
import argparse
import itertools
import sys
import warnings

import pytest
import pytest_catchlog

from qutebrowser.utils import log


@pytest.yield_fixture(autouse=True)
def restore_loggers():
    """Fixture to save/restore the logging state.

    Based on CPython's Lib/test/test_logging.py.
    """
    logging.captureWarnings(False)
    logger_dict = logging.getLogger().manager.loggerDict
    logging._acquireLock()
    try:
        saved_handlers = logging._handlers.copy()
        saved_handler_list = logging._handlerList[:]
        saved_loggers = saved_loggers = logger_dict.copy()
        saved_name_to_level = logging._nameToLevel.copy()
        saved_level_to_name = logging._levelToName.copy()
        logger_states = {}
        for name in saved_loggers:
            logger_states[name] = getattr(saved_loggers[name], 'disabled',
                                          None)
    finally:
        logging._releaseLock()

    root_logger = logging.getLogger("")
    root_handlers = root_logger.handlers[:]
    original_logging_level = root_logger.getEffectiveLevel()

    yield

    while root_logger.handlers:
        h = root_logger.handlers[0]
        root_logger.removeHandler(h)
        if not isinstance(h, pytest_catchlog.LogCaptureHandler):
            h.close()
    root_logger.setLevel(original_logging_level)
    for h in root_handlers:
        if not isinstance(h, pytest_catchlog.LogCaptureHandler):
            # https://github.com/The-Compiler/qutebrowser/issues/856
            root_logger.addHandler(h)
    logging._acquireLock()
    try:
        logging._levelToName.clear()
        logging._levelToName.update(saved_level_to_name)
        logging._nameToLevel.clear()
        logging._nameToLevel.update(saved_name_to_level)
        logging._handlers.clear()
        logging._handlers.update(saved_handlers)
        logging._handlerList[:] = saved_handler_list
        logger_dict = logging.getLogger().manager.loggerDict
        logger_dict.clear()
        logger_dict.update(saved_loggers)
        logger_states = logger_states
        for name in logger_states:
            if logger_states[name] is not None:
                saved_loggers[name].disabled = logger_states[name]
    finally:
        logging._releaseLock()


@pytest.fixture(scope='session')
def log_counter():
    """Counter for logger fixture to get unique loggers."""
    return itertools.count()


@pytest.fixture
def logger(log_counter):
    """Fixture which provides a logger for tests.

    Unique throwaway loggers are used to make sure the tests don't influence
    each other.
    """
    i = next(log_counter)
    return logging.getLogger('qutebrowser-unittest-logger-{}'.format(i))


class TestLogFilter:

    """Tests for LogFilter."""

    def _make_record(self, logger, name, level=logging.DEBUG):
        """Create a bogus logging record with the supplied logger name."""
        return logger.makeRecord(name, level=level, fn=None, lno=0, msg="",
                                 args=None, exc_info=None)

    def test_empty(self, logger):
        """Test if an empty filter lets all messages through."""
        logfilter = log.LogFilter(None)
        record = self._make_record(logger, "eggs.bacon.spam")
        assert logfilter.filter(record)
        record = self._make_record(logger, "eggs")
        assert logfilter.filter(record)

    def test_matching(self, logger):
        """Test if a filter lets an exactly matching log record through."""
        logfilter = log.LogFilter(["eggs", "bacon"])
        record = self._make_record(logger, "eggs")
        assert logfilter.filter(record)
        record = self._make_record(logger, "bacon")
        assert logfilter.filter(record)
        record = self._make_record(logger, "spam")
        assert not logfilter.filter(record)
        logfilter = log.LogFilter(["eggs.bacon"])
        record = self._make_record(logger, "eggs.bacon")
        assert logfilter.filter(record)

    def test_equal_start(self, logger):
        """Test if a filter blocks a logger which looks equal but isn't."""
        logfilter = log.LogFilter(["eggs"])
        record = self._make_record(logger, "eggsauce")
        assert not logfilter.filter(record)
        logfilter = log.LogFilter("eggs.bacon")
        record = self._make_record(logger, "eggs.baconstrips")
        assert not logfilter.filter(record)

    def test_child(self, logger):
        """Test if a filter lets through a logger which is a child."""
        logfilter = log.LogFilter(["eggs.bacon", "spam.ham"])
        record = self._make_record(logger, "eggs.bacon.spam")
        assert logfilter.filter(record)
        record = self._make_record(logger, "spam.ham.salami")
        assert logfilter.filter(record)

    def test_debug(self, logger):
        """Test if messages more important than debug are never filtered."""
        logfilter = log.LogFilter(["eggs"])
        # First check if the filter works as intended with debug messages
        record = self._make_record(logger, "eggs")
        assert logfilter.filter(record)
        record = self._make_record(logger, "bacon")
        assert not logfilter.filter(record)
        # Then check if info is not filtered
        record = self._make_record(logger, "eggs", level=logging.INFO)
        assert logfilter.filter(record)
        record = self._make_record(logger, "bacon", level=logging.INFO)
        assert logfilter.filter(record)


class TestRAMHandler:

    """Tests for RAMHandler."""

    @pytest.fixture
    def handler(self, logger):
        """Fixture providing a RAMHandler."""
        handler = log.RAMHandler(capacity=2)
        handler.setLevel(logging.NOTSET)
        logger.addHandler(handler)
        return handler

    def test_filled(self, handler, logger):
        """Test handler with exactly as much records as it can hold."""
        logger.debug("One")
        logger.debug("Two")
        assert len(handler._data) == 2
        assert handler._data[0].msg == "One"
        assert handler._data[1].msg == "Two"

    def test_overflow(self, handler, logger):
        """Test handler with more records as it can hold."""
        logger.debug("One")
        logger.debug("Two")
        logger.debug("Three")
        assert len(handler._data) == 2
        assert handler._data[0].msg == "Two"
        assert handler._data[1].msg == "Three"

    def test_dump_log(self, handler, logger):
        """Test dump_log()."""
        logger.debug("One")
        logger.debug("Two")
        logger.debug("Three")
        assert handler.dump_log() == "Two\nThree"


@pytest.mark.integration
class TestInitLog:

    """Tests for init_log."""

    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        """Mock out qInstallMessageHandler."""
        mocker.patch('qutebrowser.utils.log.QtCore.qInstallMessageHandler',
                     autospec=True)

    @pytest.fixture
    def args(self):
        """Fixture providing an argparse namespace for init_log."""
        return argparse.Namespace(debug=True, loglevel='debug', color=True,
                                  loglines=10, logfilter="", force_color=False,
                                  json_logging=False)

    def test_stderr_none(self, args):
        """Test init_log with sys.stderr = None."""
        old_stderr = sys.stderr
        sys.stderr = None
        log.init_log(args)
        sys.stderr = old_stderr


class TestHideQtWarning:

    """Tests for hide_qt_warning/QtWarningFilter."""

    @pytest.fixture()
    def logger(self):
        return logging.getLogger('qt-tests')

    def test_unfiltered(self, logger, caplog):
        """Test a message which is not filtered."""
        with log.hide_qt_warning("World", 'qt-tests'):
            with caplog.at_level(logging.WARNING, 'qt-tests'):
                logger.warning("Hello World")
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelname == 'WARNING'
        assert record.message == "Hello World"

    def test_filtered_exact(self, logger, caplog):
        """Test a message which is filtered (exact match)."""
        with log.hide_qt_warning("Hello", 'qt-tests'):
            with caplog.at_level(logging.WARNING, 'qt-tests'):
                logger.warning("Hello")
        assert not caplog.records

    def test_filtered_start(self, logger, caplog):
        """Test a message which is filtered (match at line start)."""
        with log.hide_qt_warning("Hello", 'qt-tests'):
            with caplog.at_level(logging.WARNING, 'qt-tests'):
                logger.warning("Hello World")
        assert not caplog.records

    def test_filtered_whitespace(self, logger, caplog):
        """Test a message which is filtered (match with whitespace)."""
        with log.hide_qt_warning("Hello", 'qt-tests'):
            with caplog.at_level(logging.WARNING, 'qt-tests'):
                logger.warning("  Hello World  ")
        assert not caplog.records


@pytest.mark.parametrize('suffix, expected', [
    ('', 'STUB: test_stub'),
    ('foo', 'STUB: test_stub (foo)'),
])
def test_stub(caplog, suffix, expected):
    with caplog.at_level(logging.WARNING, 'misc'):
        log.stub(suffix)
    assert len(caplog.records) == 1
    assert caplog.records[0].message == expected


def test_ignore_py_warnings(caplog):
    logging.captureWarnings(True)
    with log.ignore_py_warnings(category=UserWarning):
        warnings.warn("hidden", UserWarning)
    with caplog.at_level(logging.WARNING):
        warnings.warn("not hidden", UserWarning)
    assert len(caplog.records) == 1
    msg = caplog.records[0].message.splitlines()[0]
    assert msg.endswith("UserWarning: not hidden")
