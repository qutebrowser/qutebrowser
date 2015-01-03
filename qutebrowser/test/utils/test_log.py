# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=protected-access

"""Tests for qutebrowser.utils.log."""

import logging
import unittest
import argparse
import sys

from qutebrowser.utils import log


class BaseTest(unittest.TestCase):

    """Base class for logging tests.

    Based on CPython's Lib/test/test_logging.py.
    """

    def setUp(self):
        """Save the old logging configuration."""
        logger_dict = logging.getLogger().manager.loggerDict
        logging._acquireLock()
        try:
            self.saved_handlers = logging._handlers.copy()
            self.saved_handler_list = logging._handlerList[:]
            self.saved_loggers = saved_loggers = logger_dict.copy()
            self.logger_states = {}
            for name in saved_loggers:
                self.logger_states[name] = getattr(saved_loggers[name],
                                                   'disabled', None)
        finally:
            logging._releaseLock()

        self.root_logger = logging.getLogger("")
        self.original_logging_level = self.root_logger.getEffectiveLevel()

    def tearDown(self):
        """Restore the original logging configuration."""
        while self.root_logger.handlers:
            h = self.root_logger.handlers[0]
            self.root_logger.removeHandler(h)
            h.close()
        self.root_logger.setLevel(self.original_logging_level)
        logging._acquireLock()
        try:
            logging._handlers.clear()
            logging._handlers.update(self.saved_handlers)
            logging._handlerList[:] = self.saved_handler_list
            logger_dict = logging.getLogger().manager.loggerDict
            logger_dict.clear()
            logger_dict.update(self.saved_loggers)
            logger_states = self.logger_states
            for name in self.logger_states:
                if logger_states[name] is not None:
                    self.saved_loggers[name].disabled = logger_states[name]
        finally:
            logging._releaseLock()


class LogFilterTests(unittest.TestCase):

    """Tests for LogFilter.

    Attributes:
        logger: The logger we use to create records.
    """

    def setUp(self):
        self.logger = logging.getLogger("foo")

    def _make_record(self, name, level=logging.DEBUG):
        """Create a bogus logging record with the supplied logger name."""
        return self.logger.makeRecord(name, level=level, fn=None, lno=0,
                                      msg="", args=None, exc_info=None)

    def test_empty(self):
        """Test if an empty filter lets all messages through."""
        logfilter = log.LogFilter(None)
        record = self._make_record("eggs.bacon.spam")
        self.assertTrue(logfilter.filter(record))
        record = self._make_record("eggs")
        self.assertTrue(logfilter.filter(record))

    def test_matching(self):
        """Test if a filter lets an exactly matching logrecord through."""
        logfilter = log.LogFilter(["eggs", "bacon"])
        record = self._make_record("eggs")
        self.assertTrue(logfilter.filter(record))
        record = self._make_record("bacon")
        self.assertTrue(logfilter.filter(record))
        record = self._make_record("spam")
        self.assertFalse(logfilter.filter(record))
        logfilter = log.LogFilter(["eggs.bacon"])
        record = self._make_record("eggs.bacon")
        self.assertTrue(logfilter.filter(record))

    def test_equal_start(self):
        """Test if a filter blocks a logger which looks equal but isn't."""
        logfilter = log.LogFilter(["eggs"])
        record = self._make_record("eggsauce")
        self.assertFalse(logfilter.filter(record))
        logfilter = log.LogFilter("eggs.bacon")
        record = self._make_record("eggs.baconstrips")
        self.assertFalse(logfilter.filter(record))

    def test_child(self):
        """Test if a filter lets through a logger which is a child."""
        logfilter = log.LogFilter(["eggs.bacon", "spam.ham"])
        record = self._make_record("eggs.bacon.spam")
        self.assertTrue(logfilter.filter(record))
        record = self._make_record("spam.ham.salami")
        self.assertTrue(logfilter.filter(record))

    def test_debug(self):
        """Test if messages more important than debug are never filtered."""
        logfilter = log.LogFilter(["eggs"])
        # First check if the filter works as intended with debug messages
        record = self._make_record("eggs")
        self.assertTrue(logfilter.filter(record))
        record = self._make_record("bacon")
        self.assertFalse(logfilter.filter(record))
        # Then check if info is not filtered
        record = self._make_record("eggs", level=logging.INFO)
        self.assertTrue(logfilter.filter(record))
        record = self._make_record("bacon", level=logging.INFO)
        self.assertTrue(logfilter.filter(record))


class RAMHandlerTests(BaseTest):

    """Tests for RAMHandler.

    Attributes:
        logger: The logger we use to log to the handler.
        handler: The RAMHandler we're testing.
        old_level: The level the root logger had before executing the test.
        old_handlers: The handlers the root logger had before executing the
                      test.
    """

    def setUp(self):
        super().setUp()
        self.logger = logging.getLogger()
        self.logger.handlers = []
        self.logger.setLevel(logging.NOTSET)
        self.handler = log.RAMHandler(capacity=2)
        self.handler.setLevel(logging.NOTSET)
        self.logger.addHandler(self.handler)

    def test_filled(self):
        """Test handler with exactly as much records as it can hold."""
        self.logger.debug("One")
        self.logger.debug("Two")
        self.assertEqual(len(self.handler._data), 2)
        self.assertEqual(self.handler._data[0].msg, "One")
        self.assertEqual(self.handler._data[1].msg, "Two")

    def test_overflow(self):
        """Test handler with more records as it can hold."""
        self.logger.debug("One")
        self.logger.debug("Two")
        self.logger.debug("Three")
        self.assertEqual(len(self.handler._data), 2)
        self.assertEqual(self.handler._data[0].msg, "Two")
        self.assertEqual(self.handler._data[1].msg, "Three")

    def test_dump_log(self):
        """Test dump_log()."""
        self.logger.debug("One")
        self.logger.debug("Two")
        self.logger.debug("Three")
        self.assertEqual(self.handler.dump_log(), "Two\nThree")


class InitLogTests(BaseTest):

    """Tests for init_log."""

    def setUp(self):
        super().setUp()
        self.args = argparse.Namespace(debug=True, loglevel=logging.DEBUG,
                                       color=True, loglines=10, logfilter="")

    def test_stderr_none(self):
        """Test init_log with sys.stderr = None."""
        old_stderr = sys.stderr
        sys.stderr = None
        log.init_log(self.args)
        sys.stderr = old_stderr

if __name__ == '__main__':
    unittest.main()
