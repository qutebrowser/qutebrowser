# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


@pytest.yield_fixture
def reset_standarddir(no_cachedir_tag):
    """Clean up standarddir arguments before and after each test."""
    standarddir.init(None)
    yield
    standarddir.init(None)


@pytest.mark.usefixtures('reset_standarddir')
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


@pytest.mark.usefixtures('reset_standarddir')
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


@pytest.mark.usefixtures('reset_standarddir')
class TestStandardDir:

    """Tests for standarddir."""

    @pytest.mark.parametrize('func, varname', [
        (standarddir.data, 'XDG_DATA_HOME'),
        (standarddir.config, 'XDG_CONFIG_HOME'),
        (standarddir.cache, 'XDG_CACHE_HOME'),
    ])
    @pytest.mark.linux
    def test_linux_explicit(self, monkeypatch, tmpdir, func, varname):
        """Test dirs with XDG environment variables explicitly set.

        Args:
            func: The function to test.
            varname: The environment variable which should be set.
        """
        monkeypatch.setenv(varname, str(tmpdir))
        assert func() == str(tmpdir / 'qute_test')

    @pytest.mark.parametrize('func, subdirs', [
        (standarddir.data, ['.local', 'share', 'qute_test']),
        (standarddir.config, ['.config', 'qute_test']),
        (standarddir.cache, ['.cache', 'qute_test']),
        (standarddir.download, ['Downloads']),
    ])
    @pytest.mark.linux
    def test_linux_normal(self, monkeypatch, tmpdir, func, subdirs):
        """Test dirs with XDG_*_HOME not set."""
        monkeypatch.setenv('HOME', str(tmpdir))
        for var in ['DATA', 'CONFIG', 'CACHE']:
            monkeypatch.delenv('XDG_{}_HOME'.format(var), raising=False)
        assert func() == str(tmpdir.join(*subdirs))

    @pytest.mark.parametrize('func, elems, expected', [
        (standarddir.data, 2, ['qute_test', 'data']),
        (standarddir.config, 1, ['qute_test']),
        (standarddir.cache, 2, ['qute_test', 'cache']),
        (standarddir.download, 1, ['Downloads']),
    ])
    @pytest.mark.windows
    def test_windows(self, func, elems, expected):
        assert func().split(os.sep)[-elems:] == expected

    @pytest.mark.parametrize('func, elems, expected', [
        (standarddir.data, 2, ['Application Support', 'qute_test']),
        (standarddir.config, 1, ['qute_test']),
        (standarddir.cache, 2, ['Caches', 'qute_test']),
        (standarddir.download, 1, ['Downloads']),
    ])
    @pytest.mark.osx
    def test_os_x(self, func, elems, expected):
        assert func().split(os.sep)[-elems:] == expected


DirArgTest = collections.namedtuple('DirArgTest', 'arg, expected')


@pytest.mark.usefixtures('reset_standarddir')
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
                                     datadir=None, basedir=None)
        standarddir.init(args)
        assert standarddir.config() == testcase.expected

    def test_cachedir(self, testcase):
        """Test --cachedir."""
        args = types.SimpleNamespace(confdir=None, cachedir=testcase.arg,
                                     datadir=None, basedir=None)
        standarddir.init(args)
        assert standarddir.cache() == testcase.expected

    def test_datadir(self, testcase):
        """Test --datadir."""
        args = types.SimpleNamespace(confdir=None, cachedir=None,
                                     datadir=testcase.arg, basedir=None)
        standarddir.init(args)
        assert standarddir.data() == testcase.expected

    def test_confdir_none(self, mocker):
        """Test --confdir with None given."""
        # patch makedirs to a noop so we don't really create a directory
        mocker.patch('qutebrowser.utils.standarddir.os.makedirs')
        args = types.SimpleNamespace(confdir=None, cachedir=None, datadir=None,
                                     basedir=None)
        standarddir.init(args)
        assert standarddir.config().split(os.sep)[-1] == 'qute_test'

    def test_runtimedir(self, tmpdir, monkeypatch):
        """Test runtime dir (which has no args)."""
        monkeypatch.setattr(
            'qutebrowser.utils.standarddir.QStandardPaths.writableLocation',
            lambda _typ: str(tmpdir))
        args = types.SimpleNamespace(confdir=None, cachedir=None, datadir=None,
                                     basedir=None)
        standarddir.init(args)
        assert standarddir.runtime() == str(tmpdir / 'qute_test')

    @pytest.mark.parametrize('typ', ['config', 'data', 'cache', 'download',
                                     pytest.mark.linux('runtime')])
    def test_basedir(self, tmpdir, typ):
        """Test --basedir."""
        expected = str(tmpdir / typ)
        args = types.SimpleNamespace(basedir=str(tmpdir))
        standarddir.init(args)
        func = getattr(standarddir, typ)
        assert func() == expected


class TestInitCacheDirTag:

    """Tests for _init_cachedir_tag."""

    def test_no_cache_dir(self, mocker, monkeypatch):
        """Smoke test with cache() returning None."""
        monkeypatch.setattr('qutebrowser.utils.standarddir.cache',
                            lambda: None)
        mocker.patch('builtins.open', side_effect=AssertionError)
        standarddir._init_cachedir_tag()

    def test_existent_cache_dir_tag(self, tmpdir, mocker, monkeypatch):
        """Test with an existent CACHEDIR.TAG."""
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
        with caplog.at_level(logging.ERROR, 'init'):
            standarddir._init_cachedir_tag()
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Failed to create CACHEDIR.TAG'
        assert not tmpdir.listdir()


class TestCreatingDir:

    """Make sure inexistent directories are created properly."""

    DIR_TYPES = ['config', 'data', 'cache', 'download', 'runtime']

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

    @pytest.mark.usefixtures('reset_standarddir')
    @pytest.mark.parametrize('typ', DIR_TYPES)
    def test_exists_race_condition(self, mocker, tmpdir, typ):
        """Make sure there can't be a TOCTOU issue when creating the file.

        See https://github.com/The-Compiler/qutebrowser/issues/942.
        """
        (tmpdir / typ).ensure(dir=True)

        m = mocker.patch('qutebrowser.utils.standarddir.os')
        m.makedirs = os.makedirs
        m.sep = os.sep
        m.path.join = os.path.join
        m.path.exists.return_value = False

        args = types.SimpleNamespace(basedir=str(tmpdir))
        standarddir.init(args)

        func = getattr(standarddir, typ)
        func()


@pytest.mark.usefixtures('reset_standarddir')
class TestSystemData:

    """Test system data path."""

    def test_system_datadir_exist_linux(self, monkeypatch):
        """Test that /usr/share/qutebrowser is used if path exists."""
        monkeypatch.setattr('sys.platform', "linux")
        monkeypatch.setattr(os.path, 'exists', lambda path: True)
        assert standarddir.system_data() == "/usr/share/qutebrowser"

    @pytest.mark.linux
    def test_system_datadir_not_exist_linux(self, monkeypatch, tmpdir,
                                            fake_args):
        """Test that system-wide path isn't used on linux if path not exist."""
        fake_args.basedir = str(tmpdir)
        standarddir.init(fake_args)
        monkeypatch.setattr(os.path, 'exists', lambda path: False)
        assert standarddir.system_data() == standarddir.data()

    def test_system_datadir_unsupportedos(self, monkeypatch, tmpdir,
                                          fake_args):
        """Test that system-wide path is not used on non-Linux OS."""
        fake_args.basedir = str(tmpdir)
        standarddir.init(fake_args)
        monkeypatch.setattr('sys.platform', "potato")
        assert standarddir.system_data() == standarddir.data()
