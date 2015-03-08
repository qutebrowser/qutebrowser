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

# pylint: disable=protected-access

"""Tests for qutebrowser.misc.lineparser."""

import io
import os
import unittest
from unittest import mock

from qutebrowser.misc import lineparser


class LineParserWrapper:

    """A wrapper over lineparser.BaseLineParser to make it testable."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._data = None
        self._test_save_prepared = False

    def _open(self, mode):
        """Override _open to use StringIO/BytesIO instead of a real file."""
        if mode not in 'rwa':
            raise ValueError("Unknown mode {!r}!".format(mode))
        if self._test_save_prepared:
            self._test_save_prepared = False
        elif mode != 'r':
            raise ValueError("Doing unprepared save!")

        if mode in 'ar' and self._data is not None:
            prev_val = self._data
        else:
            prev_val = None

        if self._binary:  # pylint: disable=no-member
            fobj = io.BytesIO(prev_val)
        else:
            fobj = io.StringIO(prev_val)

        if mode == 'a':
            fobj.seek(0, os.SEEK_END)
        return fobj

    def _write(self, fp, data):
        """Extend _write to get the data after writing it."""
        super()._write(fp, data)
        self._data = fp.getvalue()

    def _prepare_save(self):
        """Keep track if _prepare_save has been called."""
        self._test_save_prepared = True


class TestableAppendLineParser(LineParserWrapper, lineparser.AppendLineParser):

    """Wrapper over AppendLineParser to make it testable."""

    pass


class TestableLineParser(LineParserWrapper, lineparser.LineParser):

    """Wrapper over LineParser to make it testable."""

    pass


class TestableLimitLineParser(LineParserWrapper, lineparser.LimitLineParser):

    """Wrapper over LimitLineParser to make it testable."""

    pass


@mock.patch('qutebrowser.misc.lineparser.os.path')
@mock.patch('qutebrowser.misc.lineparser.os')
class BaseLineParserTests(unittest.TestCase):

    """Tests for BaseLineParser."""

    def setUp(self):
        self._confdir = "this really doesn't matter"
        self._fname = "and neither does this"
        self._lineparser = lineparser.BaseLineParser(
            self._confdir, self._fname)

    def test_prepare_save_existing(self, os_mock, os_path_mock):
        """Test if _prepare_save does what it's supposed to do."""
        os_path_mock.exists.return_value = True
        self._lineparser._prepare_save()
        self.assertFalse(os_mock.makedirs.called)

    def test_prepare_save_missing(self, os_mock, os_path_mock):
        """Test if _prepare_save does what it's supposed to do."""
        os_path_mock.exists.return_value = False
        self._lineparser._prepare_save()
        os_mock.makedirs.assert_called_with(self._confdir, 0o755)


class AppendLineParserTests(unittest.TestCase):

    """Tests for AppendLineParser."""

    def setUp(self):
        self._lineparser = TestableAppendLineParser('this really',
                                                    'does not matter')
        self._lineparser.new_data = ['old data 1', 'old data 2']
        self._expected_data = self._lineparser.new_data
        self._lineparser.save()

    def _get_expected(self):
        """Get the expected data with newlines."""
        return '\n'.join(self._expected_data) + '\n'

    def test_save(self):
        """Test save()."""
        self._lineparser.new_data = ['new data 1', 'new data 2']
        self._expected_data += self._lineparser.new_data
        self._lineparser.save()
        self.assertEqual(self._lineparser._data, self._get_expected())

    def test_iter_without_open(self):
        """Test __iter__ without having called open()."""
        with self.assertRaises(ValueError):
            iter(self._lineparser)

    def test_iter(self):
        """Test __iter__."""
        self._lineparser.new_data = ['new data 1', 'new data 2']
        self._expected_data += self._lineparser.new_data
        with self._lineparser.open():
            self.assertEqual(list(self._lineparser), self._expected_data)

    @mock.patch('qutebrowser.misc.lineparser.AppendLineParser._open')
    def test_iter_not_found(self, open_mock):
        """Test __iter__ with no file."""
        open_mock.side_effect = FileNotFoundError
        linep = lineparser.AppendLineParser('foo', 'bar')
        linep.new_data = ['new data 1', 'new data 2']
        expected_data = linep.new_data
        with linep.open():
            self.assertEqual(list(linep), expected_data)

    def test_get_recent_none(self):
        """Test get_recent with no data."""
        linep = TestableAppendLineParser('this really', 'does not matter')
        self.assertEqual(linep.get_recent(), [])

    def test_get_recent_little(self):
        """Test get_recent with little data."""
        data = [e + '\n' for e in self._expected_data]
        self.assertEqual(self._lineparser.get_recent(), data)

    def test_get_recent_much(self):
        """Test get_recent with much data."""
        size = 64
        new_data = ['new data {}'.format(i) for i in range(size)]
        self._lineparser.new_data = new_data
        self._lineparser.save()
        data = '\n'.join(self._expected_data + new_data)
        data = [e + '\n' for e in data[-(size - 1):].splitlines()]
        self.assertEqual(self._lineparser.get_recent(size), data)


if __name__ == '__main__':
    unittest.main()
