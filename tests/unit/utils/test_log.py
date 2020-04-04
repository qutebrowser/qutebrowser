# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import attr
import pytest
import _pytest.logging
from PyQt5 import QtCore

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
        if not isinstance(h, _pytest.logging.LogCaptureHandler):
            h.close()
    root_logger.setLevel(original_logging_level)
    for h in root_handlers:
        if not isinstance(h, _pytest.logging.LogCaptureHandler):
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

    @pytest.mark.parametrize('filters, negated, category, logged', [
        # Filter letting all messages through
        (None, False, 'eggs.bacon.spam', True),
        (None, False, 'eggs', True),
        (None, True, 'ham', True),
        # Matching records
        (['eggs', 'bacon'], False, 'eggs', True),
        (['eggs', 'bacon'], False, 'bacon', True),
        (['eggs.bacon'], False, 'eggs.bacon', True),
        # Non-matching records
        (['eggs', 'bacon'], False, 'spam', False),
        (['eggs'], False, 'eggsauce', False),
        (['eggs.bacon'], False, 'eggs.baconstrips', False),
        # Child loggers
        (['eggs.bacon', 'spam.ham'], False, 'eggs.bacon.spam', True),
        (['eggs.bacon', 'spam.ham'], False, 'spam.ham.salami', True),
        # Suppressed records
        (['eggs', 'bacon'], True, 'eggs', False),
        (['eggs', 'bacon'], True, 'bacon', False),
        (['eggs.bacon'], True, 'eggs.bacon', False),
        # Non-suppressed records
        (['eggs', 'bacon'], True, 'spam', True),
        (['eggs'], True, 'eggsauce', True),
        (['eggs.bacon'], True, 'eggs.baconstrips', True),
    ])
    def test_logfilter(self, logger, filters, negated, category, logged):
        """Ensure the multi-record filtering filterer filters multiple records.

        (Blame @toofar for this comment)
        """
        logfilter = log.LogFilter(filters, negated)
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

    def _get_default_args(self):
        return argparse.Namespace(debug=True, loglevel='debug', color=True,
                                  loglines=10, logfilter="", force_color=False,
                                  json_logging=False, debug_flags=set())

    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        mocker.patch('qutebrowser.utils.log.QtCore.qInstallMessageHandler',
                     autospec=True)
        yield
        # Make sure logging is in a sensible default state
        args = self._get_default_args()
        log.init_log(args)

    @pytest.fixture
    def args(self):
        """Fixture providing an argparse namespace for init_log."""
        return self._get_default_args()

    def test_stderr_none(self, args):
        """Test init_log with sys.stderr = None."""
        old_stderr = sys.stderr
        sys.stderr = None
        log.init_log(args)
        sys.stderr = old_stderr

    @pytest.mark.parametrize('logfilter, expected_names, negated', [
        ('!one,two', ['one', 'two'], True),
        ('one,two', ['one', 'two'], False),
        ('one,!two', ['one', '!two'], False),
        (None, None, False),
    ])
    def test_negation_parser(self, args, mocker,
                             logfilter, expected_names, negated):
        """Test parsing the --logfilter argument."""
        filter_mock = mocker.patch('qutebrowser.utils.log.LogFilter',
                                   autospec=True)
        args.logfilter = logfilter
        log.init_log(args)
        assert filter_mock.called
        assert filter_mock.call_args[0] == (expected_names, negated)

    def test_python_warnings(self, args, caplog):
        log.init_log(args)

        with caplog.at_level(logging.WARNING):
            warnings.warn("test warning", PendingDeprecationWarning)

        expected = "PendingDeprecationWarning: test warning"
        assert expected in caplog.records[0].message

    def test_python_warnings_werror(self, args):
        args.debug_flags = {'werror'}
        log.init_log(args)

        with pytest.raises(PendingDeprecationWarning):
            warnings.warn("test warning", PendingDeprecationWarning)


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
    assert caplog.messages == [expected]


def test_ignore_py_warnings(caplog):
    logging.captureWarnings(True)
    with log.ignore_py_warnings(category=UserWarning):
        warnings.warn("hidden", UserWarning)
    with caplog.at_level(logging.WARNING):
        warnings.warn("not hidden", UserWarning)
    assert len(caplog.records) == 1
    msg = caplog.messages[0].splitlines()[0]
    assert msg.endswith("UserWarning: not hidden")


class TestQtMessageHandler:

    @attr.s
    class Context:

        """Fake QMessageLogContext."""

        function = attr.ib(default=None)
        category = attr.ib(default=None)
        file = attr.ib(default=None)
        line = attr.ib(default=None)

    def test_empty_message(self, caplog):
        """Make sure there's no crash with an empty message."""
        log.qt_message_handler(QtCore.QtDebugMsg, self.Context(), "")
        assert caplog.messages == ["Logged empty message!"]
