# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import unittest
from unittest import TestCase

import qutebrowser.utils.log as log


class LogFilterTests(TestCase):

    """Tests for LogFilter.

    Attributes:
        logger: The logger we use to create records.
    """

    def setUp(self):
        self.logger = logging.getLogger("foo")

    def _make_record(self, name, level=logging.INFO):
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
        record = self._make_record("eggs", level=logging.DEBUG)
        self.assertTrue(logfilter.filter(record))
        record = self._make_record("bacon", level=logging.DEBUG)
        self.assertFalse(logfilter.filter(record))
        # Then check if info is not filtered
        record = self._make_record("eggs", level=logging.INFO)
        self.assertTrue(logfilter.filter(record))
        record = self._make_record("bacon", level=logging.INFO)
        self.assertTrue(logfilter.filter(record))


class RAMHandlerTests(TestCase):

    """Tests for RAMHandler.

    Attributes:
        logger: The logger we use to log to the handler.
        handler: The RAMHandler we're testing.
        old_level: The level the root logger had before executing the test.
        old_handlers: The handlers the root logger had before executing the
                      test.
    """

    def setUp(self):
        self.logger = logging.getLogger()
        self.old_level = self.logger.level
        self.old_handlers = self.logger.handlers
        self.logger.handlers = []
        self.logger.setLevel(logging.NOTSET)
        self.handler = log.RAMHandler(capacity=2)
        self.handler.setLevel(logging.NOTSET)
        self.logger.addHandler(self.handler)

    def test_filled(self):
        """Test handler with exactly as much records as it can hold."""
        self.logger.debug("One")
        self.logger.debug("Two")
        self.assertEqual(len(self.handler.data), 2)
        self.assertEqual(self.handler.data[0].msg, "One")
        self.assertEqual(self.handler.data[1].msg, "Two")

    def test_overflow(self):
        """Test handler with more records as it can hold."""
        self.logger.debug("One")
        self.logger.debug("Two")
        self.logger.debug("Three")
        self.assertEqual(len(self.handler.data), 2)
        self.assertEqual(self.handler.data[0].msg, "Two")
        self.assertEqual(self.handler.data[1].msg, "Three")

    def test_dump_log(self):
        """Test dump_log()."""
        self.logger.debug("One")
        self.logger.debug("Two")
        self.logger.debug("Three")
        self.assertEqual(self.handler.dump_log(), "Two\nThree")

    def tearDown(self):
        """Restore the original root logger level and handlers."""
        self.logger.level = self.old_level
        self.logger.handlers = self.old_handlers


if __name__ == '__main__':
    unittest.main()
