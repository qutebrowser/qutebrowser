# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from unittest import mock

import pytest

from qutebrowser.misc import lineparser as lineparsermod


class TestBaseLineParser:

    CONFDIR = "this really doesn't matter"
    FILENAME = "and neither does this"

    @pytest.fixture
    def lineparser(self):
        """Fixture providing a BaseLineParser."""
        return lineparsermod.BaseLineParser(self.CONFDIR, self.FILENAME)

    def test_prepare_save_missing(self, mocker, lineparser):
        """Test if _prepare_save does what it's supposed to do."""
        os_mock = mocker.patch('qutebrowser.misc.lineparser.os')
        lineparser._prepare_save()
        os_mock.makedirs.assert_called_with(self.CONFDIR, 0o755, exist_ok=True)

    def test_double_open(self, mocker, lineparser):
        """Test if _open refuses reentry."""
        mocker.patch('builtins.open', mock.mock_open())

        with lineparser._open('r'):
            with pytest.raises(IOError,
                               match="Refusing to double-open LineParser."):
                with lineparser._open('r'):
                    pass

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
            with pytest.raises(IOError,
                               match="Refusing to double-open LineParser."):
                lineparser.save()

    def test_prepare_save(self, tmpdir, lineparser):
        """Test if save() bails when _prepare_save() returns False."""
        (tmpdir / 'file').write('pristine\n')
        lineparser.data = ['changed']
        lineparser._prepare_save = lambda: False
        lineparser.save()
        assert (tmpdir / 'file').read() == 'pristine\n'
