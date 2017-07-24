# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from qutebrowser.misc import utilcmds


@pytest.fixture(autouse=True)
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
            # https://github.com/qutebrowser/qutebrowser/issues/856
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

    def _make_record(self, logger, name, level=logging.DEBUG):
        """Create a bogus logging record with the supplied logger name."""
        return logger.makeRecord(name, level=level, fn=None, lno=0, msg="",
                                 args=None, exc_info=None)

    @pytest.mark.parametrize('filters, category, logged', [
        # Filter letting all messages through
        (None, 'eggs.bacon.spam', True),
        (None, 'eggs', True),
        # Matching records
        (['eggs', 'bacon'], 'eggs', True),
        (['eggs', 'bacon'], 'bacon', True),
        (['eggs.bacon'], 'eggs.bacon', True),
        # Non-matching records
        (['eggs', 'bacon'], 'spam', False),
        (['eggs'], 'eggsauce', False),
        (['eggs.bacon'], 'eggs.baconstrips', False),
        # Child loggers
        (['eggs.bacon', 'spam.ham'], 'eggs.bacon.spam', True),
        (['eggs.bacon', 'spam.ham'], 'spam.ham.salami', True),
    ])
    def test_logfilter(self, logger, filters, category, logged):
        logfilter = log.LogFilter(filters)
        record = self._make_record(logger, category)
        assert logfilter.filter(record) == logged

    @pytest.mark.parametrize('category', ['eggs', 'bacon'])
    def test_debug(self, logger, category):
        """Test if messages more important than debug are never filtered."""
        logfilter = log.LogFilter(['eggs'])
        record = self._make_record(logger, category, level=logging.INFO)
        assert logfilter.filter(record)

    @pytest.mark.parametrize('category, logged_before, logged_after', [
        ('init', True, False), ('url', False, True), ('js', False, True)])
    def test_debug_log_filter_cmd(self, monkeypatch, logger, category,
                                  logged_before, logged_after):
        """Test the :debug-log-filter command handler."""
        logfilter = log.LogFilter(["init"])
        monkeypatch.setattr(log, 'console_filter', logfilter)

        record = self._make_record(logger, category)

        assert logfilter.filter(record) == logged_before
        utilcmds.debug_log_filter('url,js')
        assert logfilter.filter(record) == logged_after


@pytest.mark.parametrize('data, expected', [
    # Less data
    (['one'], ['one']),
    # Exactly filled
    (['one', 'two'], ['one', 'two']),
    # More data
    (['one', 'two', 'three'], ['two', 'three']),
])
def test_ram_handler(logger, data, expected):
    handler = log.RAMHandler(capacity=2)
    handler.setLevel(logging.NOTSET)
    logger.addHandler(handler)

    for line in data:
        logger.debug(line)

    assert [rec.msg for rec in handler._data] == expected
    assert handler.dump_log() == '\n'.join(expected)


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
    def qt_logger(self):
        return logging.getLogger('qt-tests')

    def test_unfiltered(self, qt_logger, caplog):
        with log.hide_qt_warning("World", 'qt-tests'):
            with caplog.at_level(logging.WARNING, 'qt-tests'):
                qt_logger.warning("Hello World")
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelname == 'WARNING'
        assert record.message == "Hello World"

    @pytest.mark.parametrize('line', [
        "Hello",  # exact match
        "Hello World",  # match at start of line
        "  Hello World  ",  # match with spaces
    ])
    def test_filtered(self, qt_logger, caplog, line):
        with log.hide_qt_warning("Hello", 'qt-tests'):
            with caplog.at_level(logging.WARNING, 'qt-tests'):
                qt_logger.warning(line)
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
