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


@pytest.fixture(autouse=True)
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


@pytest.fixture
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
        with pytest.raises(standarddir.EmptyValueError):
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
        (standarddir.runtime, 'XDG_RUNTIME_DIR'),
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

    @pytest.mark.linux
    @pytest.mark.qt_log_ignore(r'^QStandardPaths: ')
    def test_linux_invalid_runtimedir(self, monkeypatch, tmpdir):
        """With invalid XDG_RUNTIME_DIR, fall back to TempLocation."""
        monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmpdir / 'does-not-exist'))
        monkeypatch.setenv('TMPDIR', str(tmpdir / 'temp'))
        assert standarddir.runtime() == str(tmpdir / 'temp' / 'qute_test')

    def test_runtimedir_empty_tempdir(self, monkeypatch, tmpdir):
        """With an empty tempdir on non-Linux, we should raise."""
        monkeypatch.setattr(standarddir.sys, 'platform', 'nt')
        monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                            lambda typ: '')
        with pytest.raises(standarddir.EmptyValueError):
            standarddir.runtime()

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

    """Tests the --basedir argument."""

    @pytest.mark.parametrize('typ', ['config', 'data', 'cache', 'download',
                                     pytest.mark.linux('runtime')])
    def test_basedir(self, tmpdir, typ):
        """Test --basedir."""
        expected = str(tmpdir / typ)
        args = types.SimpleNamespace(basedir=str(tmpdir))
        standarddir.init(args)
        func = getattr(standarddir, typ)
        assert func() == expected

    def test_basedir_relative(self, tmpdir):
        """Test --basedir with a relative path."""
        basedir = (tmpdir / 'basedir')
        basedir.ensure(dir=True)
        with tmpdir.as_cwd():
            args = types.SimpleNamespace(basedir='basedir')
            standarddir.init(args)
            assert standarddir.config() == str(basedir / 'config')


class TestInitCacheDirTag:

    """Tests for _init_cachedir_tag."""

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

        See https://github.com/qutebrowser/qutebrowser/issues/942.
        """
        (tmpdir / typ).ensure(dir=True)

        m = mocker.patch('qutebrowser.utils.standarddir.os')
        m.makedirs = os.makedirs
        m.sep = os.sep
        m.path.join = os.path.join
        m.path.exists.return_value = False
        m.path.abspath = lambda x: x

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


class TestMoveWebEngineData:

    """Test moving QtWebEngine data from an old location."""

    @pytest.fixture(autouse=True)
    def patch_standardpaths(self, tmpdir, monkeypatch):
        locations = {
            QStandardPaths.DataLocation: str(tmpdir / 'data'),
            QStandardPaths.CacheLocation: str(tmpdir / 'cache'),
        }
        monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                            locations.get)
        monkeypatch.setattr(standarddir, 'data',
                            lambda: str(tmpdir / 'new_data'))
        monkeypatch.setattr(standarddir, 'cache',
                            lambda: str(tmpdir / 'new_cache'))

    @pytest.fixture
    def files(self, tmpdir):
        files = collections.namedtuple('Files', ['old_data', 'new_data',
                                                 'old_cache', 'new_cache'])
        return files(
            old_data=tmpdir / 'data' / 'QtWebEngine' / 'Default' / 'datafile',
            new_data=tmpdir / 'new_data' / 'webengine' / 'datafile',
            old_cache=(tmpdir / 'cache' / 'QtWebEngine' / 'Default' /
                       'cachefile'),
            new_cache=(tmpdir / 'new_cache' / 'webengine' / 'cachefile'),
        )

    def test_no_webengine_dir(self, caplog):
        """Nothing should happen without any QtWebEngine directory."""
        standarddir._move_webengine_data()
        assert not any(rec.message.startswith('Moving QtWebEngine')
                       for rec in caplog.records)

    def test_moving_data(self, files):
        files.old_data.ensure()
        files.old_cache.ensure()

        standarddir._move_webengine_data()

        assert not files.old_data.exists()
        assert not files.old_cache.exists()
        assert files.new_data.exists()
        assert files.new_cache.exists()

    @pytest.mark.parametrize('what', ['data', 'cache'])
    def test_already_existing(self, files, caplog, what):
        files.old_data.ensure()
        files.old_cache.ensure()

        if what == 'data':
            files.new_data.ensure()
        else:
            files.new_cache.ensure()

        with caplog.at_level(logging.WARNING):
            standarddir._move_webengine_data()

        record = caplog.records[-1]
        expected = "Failed to move old QtWebEngine {}".format(what)
        assert record.message.startswith(expected)

    def test_deleting_empty_dirs(self, monkeypatch, tmpdir):
        """When we have a qutebrowser/qutebrowser subfolder, clean it up."""
        old_data = tmpdir / 'data' / 'qutebrowser' / 'qutebrowser'
        old_cache = tmpdir / 'cache' / 'qutebrowser' / 'qutebrowser'
        locations = {
            QStandardPaths.DataLocation: str(old_data),
            QStandardPaths.CacheLocation: str(old_cache),
        }
        monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                            locations.get)

        old_data_file = old_data / 'QtWebEngine' / 'Default' / 'datafile'
        old_cache_file = old_cache / 'QtWebEngine' / 'Default' / 'cachefile'
        old_data_file.ensure()
        old_cache_file.ensure()

        standarddir._move_webengine_data()

        assert not (tmpdir / 'data' / 'qutebrowser' / 'qutebrowser').exists()
        assert not (tmpdir / 'cache' / 'qutebrowser' / 'qutebrowser').exists()

    def test_deleting_error(self, files, monkeypatch, mocker, caplog):
        """When there was an error it should be logged."""
        mock = mocker.Mock(side_effect=OSError('error'))
        monkeypatch.setattr(standarddir.shutil, 'move', mock)
        files.old_data.ensure()
        files.old_cache.ensure()

        with caplog.at_level(logging.ERROR):
            standarddir._move_webengine_data()

        record = caplog.records[-1]
        expected = "Failed to move old QtWebEngine data/cache: error"
        assert record.message == expected
