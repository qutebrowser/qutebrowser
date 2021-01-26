# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.utils.log."""

import logging
import argparse
import itertools
import sys
import warnings
import dataclasses

import pytest
import _pytest.logging
from PyQt5 import QtCore

from qutebrowser import qutebrowser
from qutebrowser.utils import log
from qutebrowser.misc import utilcmds
from qutebrowser.api import cmdutils


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
        (set(), False, 'eggs.bacon.spam', True),
        (set(), False, 'eggs', True),
        (set(), True, 'ham', True),
        # Matching records
        ({'eggs', 'bacon'}, False, 'eggs', True),
        ({'eggs', 'bacon'}, False, 'bacon', True),
        ({'eggs'}, False, 'eggs.fried', True),
        # Non-matching records
        ({'eggs', 'bacon'}, False, 'spam', False),
        ({'eggs'}, False, 'eggsauce', False),
        ({'fried'}, False, 'eggs.fried', False),
        # Suppressed records
        ({'eggs', 'bacon'}, True, 'eggs', False),
        ({'eggs', 'bacon'}, True, 'bacon', False),
        # Non-suppressed records
        ({'eggs', 'bacon'}, True, 'spam', True),
        ({'eggs'}, True, 'eggsauce', True),
    ])
    def test_logfilter(self, logger, filters, negated, category, logged):
        """Ensure the multi-record filtering filterer filters multiple records.

        (Blame @toofar for this comment)
        """
        logfilter = log.LogFilter(filters, negated=negated)
        record = self._make_record(logger, category)
        assert logfilter.filter(record) == logged

    def test_logfilter_benchmark(self, logger, benchmark):
        record = self._make_record(logger, 'unfiltered')
        filters = set(log.LOGGER_NAMES)  # Extreme case
        logfilter = log.LogFilter(filters, negated=False)
        benchmark(lambda: logfilter.filter(record))

    @pytest.mark.parametrize('only_debug', [True, False])
    def test_debug(self, logger, only_debug):
        """Test if messages more important than debug are never filtered."""
        logfilter = log.LogFilter({'eggs'}, only_debug=only_debug)
        record = self._make_record(logger, 'bacon', level=logging.INFO)
        assert logfilter.filter(record) == only_debug

    @pytest.mark.parametrize(
        'category, filter_str, logged_before, logged_after', [
            ('init', 'url,js', True, False),
            ('url', 'url,js', False, True),
            ('js', 'url,js', False, True),
            ('js', 'none', False, True),
        ]
    )
    def test_debug_log_filter_cmd(self, monkeypatch, logger, category,
                                  filter_str, logged_before, logged_after):
        """Test the :debug-log-filter command handler."""
        logfilter = log.LogFilter({"init"})
        monkeypatch.setattr(log, 'console_filter', logfilter)

        record = self._make_record(logger, category)

        assert logfilter.filter(record) == logged_before
        utilcmds.debug_log_filter('url,js')
        assert logfilter.filter(record) == logged_after

    def test_debug_log_filter_cmd_invalid(self, monkeypatch):
        logfilter = log.LogFilter(set())
        monkeypatch.setattr(log, 'console_filter', logfilter)
        with pytest.raises(cmdutils.CommandError,
                           match='Invalid log category blabla'):
            utilcmds.debug_log_filter('blabla')

    @pytest.mark.parametrize('filter_str, expected_names, negated', [
        ('!js,misc', {'js', 'misc'}, True),
        ('js,misc', {'js', 'misc'}, False),
        ('js, misc', {'js', 'misc'}, False),
        ('JS, Misc', {'js', 'misc'}, False),
        (None, set(), False),
        ('none', set(), False),
    ])
    def test_parsing(self, filter_str, expected_names, negated):
        logfilter = log.LogFilter.parse(filter_str)
        assert logfilter.names == expected_names
        assert logfilter.negated == negated

    @pytest.mark.parametrize('filter_str, invalid', [
        ('js,!misc', '!misc'),
        ('blabla,js,blablub', 'blabla, blablub'),
    ])
    def test_parsing_invalid(self, filter_str, invalid):
        with pytest.raises(
                log.InvalidLogFilterError,
                match='Invalid log category {} - '
                'valid categories: statusbar, .*'.format(invalid)):
            log.LogFilter.parse(filter_str)


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
                                  loglines=10, logfilter=None,
                                  force_color=False, json_logging=False,
                                  debug_flags=set())

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

    @pytest.fixture
    def parser(self):
        return qutebrowser.get_argparser()

    @pytest.fixture
    def empty_args(self, parser):
        """Logging commandline arguments without any customization."""
        return parser.parse_args([])

    def test_stderr_none(self, args):
        """Test init_log with sys.stderr = None."""
        old_stderr = sys.stderr
        sys.stderr = None
        log.init_log(args)
        sys.stderr = old_stderr

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

    @pytest.mark.parametrize('cli, conf, expected', [
        (None, 'info', logging.INFO),
        (None, 'warning', logging.WARNING),
        ('info', 'warning', logging.INFO),
        ('warning', 'info', logging.WARNING),
    ])
    def test_init_from_config_console(self, cli, conf, expected, args,
                                      config_stub):
        args.debug = False
        args.loglevel = cli
        log.init_log(args)

        config_stub.val.logging.level.console = conf
        log.init_from_config(config_stub.val)
        assert log.console_handler.level == expected

    @pytest.mark.parametrize('conf, expected', [
        ('vdebug', logging.VDEBUG),
        ('debug', logging.DEBUG),
        ('info', logging.INFO),
        ('critical', logging.CRITICAL),
    ])
    def test_init_from_config_ram(self, conf, expected, args, config_stub):
        args.debug = False
        log.init_log(args)

        config_stub.val.logging.level.ram = conf
        log.init_from_config(config_stub.val)
        assert log.ram_handler.level == expected

    def test_init_from_config_consistent_default(self, config_stub, empty_args):
        """Ensure config defaults are consistent with the builtin defaults."""
        log.init_log(empty_args)

        assert log.ram_handler.level == logging.DEBUG
        assert log.console_handler.level == logging.INFO

        log.init_from_config(config_stub.val)

        assert log.ram_handler.level == logging.DEBUG
        assert log.console_handler.level == logging.INFO

    def test_init_from_config_format(self, config_stub, empty_args):
        """If we change to the debug level, make sure the format changes."""
        log.init_log(empty_args)
        assert log.console_handler.formatter._fmt == log.SIMPLE_FMT

        config_stub.val.logging.level.console = 'debug'
        log.init_from_config(config_stub.val)
        assert log.console_handler.formatter._fmt == log.EXTENDED_FMT

    def test_logfilter(self, parser):
        args = parser.parse_args(['--logfilter', 'misc'])
        log.init_log(args)
        assert log.console_filter.names == {'misc'}


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


def test_py_warning_filter(caplog):
    logging.captureWarnings(True)
    with log.py_warning_filter(category=UserWarning):
        warnings.warn("hidden", UserWarning)
    with caplog.at_level(logging.WARNING):
        warnings.warn("not hidden", UserWarning)
    assert len(caplog.records) == 1
    msg = caplog.messages[0].splitlines()[0]
    assert msg.endswith("UserWarning: not hidden")


def test_py_warning_filter_error(caplog):
    warnings.simplefilter('ignore')
    warnings.warn("hidden", UserWarning)

    with log.py_warning_filter('error'):
        with pytest.raises(UserWarning):
            warnings.warn("error", UserWarning)


def test_warning_still_errors():
    # Mainly a sanity check after the tests messing with warnings above.
    with pytest.raises(UserWarning):
        warnings.warn("error", UserWarning)


class TestQtMessageHandler:

    @dataclasses.dataclass
    class Context:

        """Fake QMessageLogContext."""

        function: str = None
        category: str = None
        file: str = None
        line: int = None

    @pytest.fixture(autouse=True)
    def init_args(self):
        parser = qutebrowser.get_argparser()
        args = parser.parse_args([])
        log.init_log(args)

    def test_empty_message(self, caplog):
        """Make sure there's no crash with an empty message."""
        log.qt_message_handler(QtCore.QtDebugMsg, self.Context(), "")
        assert caplog.messages == ["Logged empty message!"]
