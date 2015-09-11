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

"""Tests for qutebrowser.utils.standarddir."""

import os
import os.path
import types
import collections
import logging
import textwrap

from PyQt5.QtCore import QStandardPaths
import pytest

from qutebrowser.utils import standarddir


@pytest.yield_fixture(autouse=True)
def change_qapp_name(qapp):
    """Change the name of the QApplication instance.

    This changes the applicationName for all tests in this module to
    "qute_test".
    """
    old_name = qapp.applicationName()
    qapp.setApplicationName('qute_test')
    yield
    qapp.setApplicationName(old_name)


@pytest.fixture
def no_cachedir_tag(monkeypatch):
    """Fixture to prevent writing a CACHEDIR.TAG."""
    monkeypatch.setattr('qutebrowser.utils.standarddir._init_cachedir_tag',
                        lambda: None)


@pytest.fixture(autouse=True)
@pytest.mark.usefixtures('no_cachedir_tag')
def reset_standarddir():
    standarddir.init(None)


@pytest.mark.parametrize('data_subdir, config_subdir, expected', [
    ('foo', 'foo', 'foo/data'),
    ('foo', 'bar', 'foo'),
])
def test_get_fake_windows_equal_dir(data_subdir, config_subdir, expected,
                                    monkeypatch, tmpdir):
    """Test _get with a fake Windows OS with equal data/config dirs."""
    locations = {
        QStandardPaths.DataLocation: str(tmpdir / data_subdir),
        QStandardPaths.ConfigLocation: str(tmpdir / config_subdir),
    }
    monkeypatch.setattr('qutebrowser.utils.standarddir.os.name', 'nt')
    monkeypatch.setattr(
        'qutebrowser.utils.standarddir.QStandardPaths.writableLocation',
        locations.get)
    expected = str(tmpdir / expected)
    assert standarddir.data() == expected


class TestWritableLocation:

    """Tests for _writable_location."""

    def test_empty(self, monkeypatch):
        """Test QStandardPaths returning an empty value."""
        monkeypatch.setattr(
            'qutebrowser.utils.standarddir.QStandardPaths.writableLocation',
            lambda typ: '')
        with pytest.raises(ValueError):
            standarddir._writable_location(QStandardPaths.DataLocation)

    def test_sep(self, monkeypatch):
        """Make sure the right kind of separator is used."""
        monkeypatch.setattr('qutebrowser.utils.standarddir.os.sep', '\\')
        loc = standarddir._writable_location(QStandardPaths.DataLocation)
        assert '/' not in loc
        assert '\\' in loc


@pytest.mark.linux
@pytest.mark.usefixtures('no_cachedir_tag')
class TestGetStandardDirLinux:

    """Tests for standarddir under Linux."""

    def test_data_explicit(self, monkeypatch, tmpdir):
        """Test data dir with XDG_DATA_HOME explicitly set."""
        monkeypatch.setenv('XDG_DATA_HOME', str(tmpdir))
        assert standarddir.data() == str(tmpdir / 'qute_test')

    def test_config_explicit(self, monkeypatch, tmpdir):
        """Test config dir with XDG_CONFIG_HOME explicitly set."""
        monkeypatch.setenv('XDG_CONFIG_HOME', str(tmpdir))
        assert standarddir.config() == str(tmpdir / 'qute_test')

    def test_cache_explicit(self, monkeypatch, tmpdir):
        """Test cache dir with XDG_CACHE_HOME explicitly set."""
        monkeypatch.setenv('XDG_CACHE_HOME', str(tmpdir))
        assert standarddir.cache() == str(tmpdir / 'qute_test')

    def test_temp_explicit(self, monkeypatch, tmpdir):
        """Test temp dir with TMPDIR explicitly set."""
        monkeypatch.setenv('TMPDIR', str(tmpdir))
        assert standarddir.temp() == str(tmpdir / 'qute_test')

    def test_data(self, monkeypatch, tmpdir):
        """Test data dir with XDG_DATA_HOME not set."""
        monkeypatch.setenv('HOME', str(tmpdir))
        monkeypatch.delenv('XDG_DATA_HOME', raising=False)
        expected = tmpdir / '.local' / 'share' / 'qute_test'
        assert standarddir.data() == str(expected)

    def test_config(self, monkeypatch, tmpdir):
        """Test config dir with XDG_CONFIG_HOME not set."""
        monkeypatch.setenv('HOME', str(tmpdir))
        monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
        expected = tmpdir / '.config' / 'qute_test'
        assert standarddir.config() == str(expected)

    def test_cache(self, monkeypatch, tmpdir):
        """Test cache dir with XDG_CACHE_HOME not set."""
        monkeypatch.setenv('HOME', str(tmpdir))
        monkeypatch.delenv('XDG_CACHE_HOME', raising=False)
        expected = tmpdir / '.cache' / 'qute_test'
        assert standarddir.cache() == expected

    def test_temp(self, monkeypatch, tmpdir):
        """Test temp dir with TMPDIR not set."""
        monkeypatch.delenv('TMPDIR', raising=False)
        assert standarddir.temp().split(os.sep)[-1] == 'qute_test'


@pytest.mark.windows
@pytest.mark.usefixtures('no_cachedir_tag')
class TestGetStandardDirWindows:

    """Tests for standarddir under Windows."""

    def test_data(self):
        """Test data dir."""
        expected = ['qute_test', 'data']
        assert standarddir.data().split(os.sep)[-2:] == expected

    def test_config(self):
        """Test config dir."""
        assert standarddir.config().split(os.sep)[-1] == 'qute_test'

    def test_cache(self):
        """Test cache dir."""
        expected = ['qute_test', 'cache']
        assert standarddir.cache().split(os.sep)[-2:] == expected

    def test_temp(self):
        assert standarddir.temp().split(os.sep)[-1] == 'qute_test'


DirArgTest = collections.namedtuple('DirArgTest', 'arg, expected')


@pytest.mark.usefixtures('no_cachedir_tag')
class TestArguments:

    """Tests with confdir/cachedir/datadir arguments."""

    @pytest.fixture(params=[DirArgTest('', None), DirArgTest('foo', 'foo')])
    def testcase(self, request, tmpdir):
        """Fixture providing testcases."""
        if request.param.expected is None:
            return request.param
        else:
            # prepend tmpdir to both
            arg = str(tmpdir / request.param.arg)
            return DirArgTest(arg, arg)

    def test_confdir(self, testcase):
        """Test --confdir."""
        args = types.SimpleNamespace(confdir=testcase.arg, cachedir=None,
                                     datadir=None)
        standarddir.init(args)
        assert standarddir.config() == testcase.expected

    def test_cachedir(self, testcase):
        """Test --cachedir."""
        args = types.SimpleNamespace(confdir=None, cachedir=testcase.arg,
                                     datadir=None)
        standarddir.init(args)
        assert standarddir.cache() == testcase.expected

    def test_datadir(self, testcase):
        """Test --datadir."""
        args = types.SimpleNamespace(confdir=None, cachedir=None,
                                     datadir=testcase.arg)
        standarddir.init(args)
        assert standarddir.data() == testcase.expected

    def test_confdir_none(self):
        """Test --confdir with None given."""
        args = types.SimpleNamespace(confdir=None, cachedir=None, datadir=None)
        standarddir.init(args)
        assert standarddir.config().split(os.sep)[-1] == 'qute_test'

    def test_runtimedir(self, tmpdir, monkeypatch):
        """Test runtime dir (which has no args)."""
        monkeypatch.setattr(
            'qutebrowser.utils.standarddir.QStandardPaths.writableLocation',
            lambda _typ: str(tmpdir))
        args = types.SimpleNamespace(confdir=None, cachedir=None, datadir=None)
        standarddir.init(args)
        assert standarddir.runtime() == str(tmpdir / 'qute_test')

    @pytest.mark.parametrize('typ', ['config', 'data', 'cache', 'download',
                                     'runtime'])
    def test_basedir(self, tmpdir, typ):
        """Test --basedir."""
        expected = str(tmpdir / typ)
        args = types.SimpleNamespace(basedir=str(tmpdir))
        standarddir.init(args)
        func = getattr(standarddir, typ)
        assert func() == expected

    def test_basedir_temp(self, tmpdir):
        """Make sure the temp file location is not influenced by basedir."""
        args = types.SimpleNamespace(basedir=str(tmpdir))
        standarddir.init(args)
        qute_tempdir = standarddir.temp()
        assert not qute_tempdir.startswith(str(tmpdir))


class TestInitCacheDirTag:

    """Tests for _init_cachedir_tag."""

    def test_no_cache_dir(self, mocker, monkeypatch):
        """Smoke test with cache() returning None."""
        monkeypatch.setattr('qutebrowser.utils.standarddir.cache',
                            lambda: None)
        mocker.patch('builtins.open', side_effect=AssertionError)
        standarddir._init_cachedir_tag()

    def test_existant_cache_dir_tag(self, tmpdir, mocker, monkeypatch):
        """Test with an existant CACHEDIR.TAG."""
        monkeypatch.setattr('qutebrowser.utils.standarddir.cache',
                            lambda: str(tmpdir))
        mocker.patch('builtins.open', side_effect=AssertionError)
        m = mocker.patch('qutebrowser.utils.standarddir.os')
        m.path.join.side_effect = os.path.join
        m.path.exists.return_value = True
        standarddir._init_cachedir_tag()
        assert not tmpdir.listdir()
        m.path.exists.assert_called_with(str(tmpdir / 'CACHEDIR.TAG'))

    def test_new_cache_dir_tag(self, tmpdir, mocker, monkeypatch):
        """Test creating a new CACHEDIR.TAG."""
        monkeypatch.setattr('qutebrowser.utils.standarddir.cache',
                            lambda: str(tmpdir))
        standarddir._init_cachedir_tag()
        assert tmpdir.listdir() == [(tmpdir / 'CACHEDIR.TAG')]
        data = (tmpdir / 'CACHEDIR.TAG').read_text('utf-8')
        assert data == textwrap.dedent("""
            Signature: 8a477f597d28d172789f06886806bc55
            # This file is a cache directory tag created by qutebrowser.
            # For information about cache directory tags, see:
            #  http://www.brynosaurus.com/cachedir/
        """).lstrip()

    def test_open_oserror(self, caplog, tmpdir, mocker, monkeypatch):
        """Test creating a new CACHEDIR.TAG."""
        monkeypatch.setattr('qutebrowser.utils.standarddir.cache',
                            lambda: str(tmpdir))
        mocker.patch('builtins.open', side_effect=OSError)
        with caplog.atLevel(logging.ERROR, 'init'):
            standarddir._init_cachedir_tag()
        assert len(caplog.records()) == 1
        assert caplog.records()[0].message == 'Failed to create CACHEDIR.TAG'
        assert not tmpdir.listdir()


class TestCreatingDir:

    """Make sure inexistant directories are created properly."""

    DIR_TYPES = ['config', 'data', 'cache', 'download', 'runtime', 'temp']

    @pytest.mark.parametrize('typ', DIR_TYPES)
    def test_basedir(self, tmpdir, typ):
        """Test --basedir."""
        basedir = tmpdir / 'basedir'
        assert not basedir.exists()
        args = types.SimpleNamespace(basedir=str(basedir))
        standarddir.init(args)

        func = getattr(standarddir, typ)
        func()

        assert basedir.exists()

        if os.name == 'posix':
            assert basedir.stat().mode & 0o777 == 0o700
