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

"""Tests for qutebrowser.misc.lineparser."""

import io
import os

import pytest

from qutebrowser.misc import lineparser as lineparsermod


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
        return True


class AppendLineParserTestable(LineParserWrapper,
                               lineparsermod.AppendLineParser):

    """Wrapper over AppendLineParser to make it testable."""

    pass


class LineParserTestable(LineParserWrapper, lineparsermod.LineParser):

    """Wrapper over LineParser to make it testable."""

    pass


class LimitLineParserTestable(LineParserWrapper,
                              lineparsermod.LimitLineParser):

    """Wrapper over LimitLineParser to make it testable."""

    pass


class TestBaseLineParser:

    """Tests for BaseLineParser."""

    CONFDIR = "this really doesn't matter"
    FILENAME = "and neither does this"

    @pytest.fixture
    def lineparser(self):
        """Fixture providing a BaseLineParser."""
        return lineparsermod.BaseLineParser(self.CONFDIR, self.FILENAME)

    def test_prepare_save_existing(self, mocker, lineparser):
        """Test if _prepare_save does what it's supposed to do."""
        os_mock = mocker.patch('qutebrowser.misc.lineparser.os')
        os_mock.path.exists.return_value = True

        lineparser._prepare_save()
        assert not os_mock.makedirs.called

    def test_prepare_save_missing(self, mocker, lineparser):
        """Test if _prepare_save does what it's supposed to do."""
        os_mock = mocker.patch('qutebrowser.misc.lineparser.os')
        os_mock.path.exists.return_value = False

        lineparser._prepare_save()
        os_mock.makedirs.assert_called_with(self.CONFDIR, 0o755)


class TestAppendLineParser:

    """Tests for AppendLineParser."""

    BASE_DATA = ['old data 1', 'old data 2']

    @pytest.fixture
    def lineparser(self):
        """Fixture to get an AppendLineParser for tests."""
        lp = AppendLineParserTestable('this really', 'does not matter')
        lp.new_data = self.BASE_DATA
        lp.save()
        return lp

    def _get_expected(self, new_data):
        """Get the expected data with newlines."""
        return '\n'.join(self.BASE_DATA + new_data) + '\n'

    def test_save(self, lineparser):
        """Test save()."""
        new_data = ['new data 1', 'new data 2']
        lineparser.new_data = new_data
        lineparser.save()
        assert lineparser._data == self._get_expected(new_data)

    def test_iter_without_open(self, lineparser):
        """Test __iter__ without having called open()."""
        with pytest.raises(ValueError):
            iter(lineparser)

    def test_iter(self, lineparser):
        """Test __iter__."""
        new_data = ['new data 1', 'new data 2']
        lineparser.new_data = new_data
        with lineparser.open():
            assert list(lineparser) == self.BASE_DATA + new_data

    def test_iter_not_found(self, mocker):
        """Test __iter__ with no file."""
        open_mock = mocker.patch(
            'qutebrowser.misc.lineparser.AppendLineParser._open')
        open_mock.side_effect = FileNotFoundError
        new_data = ['new data 1', 'new data 2']
        linep = lineparsermod.AppendLineParser('foo', 'bar')
        linep.new_data = new_data
        with linep.open():
            assert list(linep) == new_data

    def test_get_recent_none(self):
        """Test get_recent with no data."""
        linep = AppendLineParserTestable('this really', 'does not matter')
        assert linep.get_recent() == []

    def test_get_recent_little(self, lineparser):
        """Test get_recent with little data."""
        data = [e + '\n' for e in self.BASE_DATA]
        assert lineparser.get_recent() == data

    def test_get_recent_much(self, lineparser):
        """Test get_recent with much data."""
        size = 64
        new_data = ['new data {}'.format(i) for i in range(size)]
        lineparser.new_data = new_data
        lineparser.save()
        data = '\n'.join(self.BASE_DATA + new_data)
        data = [e + '\n' for e in data[-(size - 1):].splitlines()]
        assert lineparser.get_recent(size) == data
