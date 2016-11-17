# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os
import pytest
from unittest import mock

from qutebrowser.misc import lineparser as lineparsermod


class TestBaseLineParser:

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

    def test_double_open(self, mocker, lineparser):
        """Test if _open refuses reentry."""
        mocker.patch('builtins.open', mock.mock_open())

        with lineparser._open('r'):
            with pytest.raises(IOError) as excinf:
                with lineparser._open('r'):
                    pass
        assert str(excinf.value) == 'Refusing to double-open AppendLineParser.'

    def test_binary(self, mocker):
        """Test if _open and _write correctly handle binary files."""
        open_mock = mock.mock_open()
        mocker.patch('builtins.open', open_mock)

        testdata = b'\xf0\xff'

        lineparser = lineparsermod.BaseLineParser(
            self.CONFDIR, self.FILENAME, binary=True)
        with lineparser._open('r') as f:
            lineparser._write(f, [testdata])

        open_mock.assert_called_once_with(
            os.path.join(self.CONFDIR, self.FILENAME), 'rb')

        open_mock().write.assert_has_calls([
            mock.call(testdata),
            mock.call(b'\n')
        ])


class TestLineParser:

    @pytest.fixture
    def lineparser(self, tmpdir):
        """Fixture to get a LineParser for tests."""
        lp = lineparsermod.LineParser(str(tmpdir), 'file')
        lp.save()
        return lp

    def test_init(self, tmpdir):
        """Test if creating a line parser correctly reads its file."""
        (tmpdir / 'file').write('one\ntwo\n')
        lineparser = lineparsermod.LineParser(str(tmpdir), 'file')
        assert lineparser.data == ['one', 'two']

        (tmpdir / 'file').write_binary(b'\xfe\n\xff\n')
        lineparser = lineparsermod.LineParser(str(tmpdir), 'file', binary=True)
        assert lineparser.data == [b'\xfe', b'\xff']

    def test_clear(self, tmpdir, lineparser):
        """Test if clear() empties its file."""
        lineparser.data = ['one', 'two']
        lineparser.save()
        assert (tmpdir / 'file').read() == 'one\ntwo\n'
        lineparser.clear()
        assert not lineparser.data
        assert (tmpdir / 'file').read() == ''

    def test_double_open(self, lineparser):
        """Test if save() bails on an already open file."""
        with lineparser._open('r'):
            with pytest.raises(IOError):
                lineparser.save()

    def test_prepare_save(self, tmpdir, lineparser):
        """Test if save() bails when _prepare_save() returns False."""
        (tmpdir / 'file').write('pristine\n')
        lineparser.data = ['changed']
        lineparser._prepare_save = lambda: False
        lineparser.save()
        assert (tmpdir / 'file').read() == 'pristine\n'


class TestAppendLineParser:

    BASE_DATA = ['old data 1', 'old data 2']

    @pytest.fixture
    def lineparser(self, tmpdir):
        """Fixture to get an AppendLineParser for tests."""
        lp = lineparsermod.AppendLineParser(str(tmpdir), 'file')
        lp.new_data = self.BASE_DATA
        lp.save()
        return lp

    def _get_expected(self, new_data):
        """Get the expected data with newlines."""
        return '\n'.join(self.BASE_DATA + new_data) + '\n'

    def test_save(self, tmpdir, lineparser):
        """Test save()."""
        new_data = ['new data 1', 'new data 2']
        lineparser.new_data = new_data
        lineparser.save()
        assert (tmpdir / 'file').read() == self._get_expected(new_data)

    def test_clear(self, tmpdir, lineparser):
        """Check if calling clear() empties both pending and persisted data."""
        lineparser.new_data = ['one', 'two']
        lineparser.save()
        assert (tmpdir / 'file').read() == "old data 1\nold data 2\none\ntwo\n"

        lineparser.new_data = ['one', 'two']
        lineparser.clear()
        lineparser.save()
        assert not lineparser.new_data
        assert (tmpdir / 'file').read() == ""

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

    def test_get_recent_none(self, tmpdir):
        """Test get_recent with no data."""
        (tmpdir / 'file2').ensure()
        linep = lineparsermod.AppendLineParser(str(tmpdir), 'file2')
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
        data = os.linesep.join(self.BASE_DATA + new_data) + os.linesep
        data = [e + '\n' for e in data[-size:].splitlines()]
        assert lineparser.get_recent(size) == data
