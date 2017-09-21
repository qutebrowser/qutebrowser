# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import sys
import os.path
import types
import collections
import logging
import textwrap

from PyQt5.QtCore import QStandardPaths
import pytest

from qutebrowser.utils import standarddir


pytestmark = pytest.mark.usefixtures('qapp')


@pytest.fixture(autouse=True)
def clear_standarddir_cache(monkeypatch):
    """Make sure the standarddir cache is cleared before/after each test."""
    monkeypatch.setattr(standarddir, '_locations', {})
    yield
    monkeypatch.setattr(standarddir, '_locations', {})


def test_fake_mac_config(tmpdir, monkeypatch):
    """Test standardir.config on a fake Mac."""
    monkeypatch.setattr(sys, 'platform', 'darwin')
    monkeypatch.setenv('HOME', str(tmpdir))
    expected = str(tmpdir) + '/.qutebrowser'  # always with /
    standarddir._init_config(args=None)
    assert standarddir.config() == expected


# FIXME:conf needs AppDataLocation
@pytest.mark.qt55
@pytest.mark.parametrize('what', ['data', 'config'])
@pytest.mark.not_mac
def test_fake_windows_data_config(tmpdir, monkeypatch, what):
    """Make sure the config is correct on a fake Windows."""
    monkeypatch.setattr(os, 'name', 'nt')
    monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                        lambda typ: str(tmpdir))
    standarddir._init_config(args=None)
    standarddir._init_data(args=None)
    func = getattr(standarddir, what)
    assert func() == str(tmpdir / what)


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
        monkeypatch.setattr(standarddir.os, 'sep', '\\')
        loc = standarddir._writable_location(QStandardPaths.DataLocation)
        assert '/' not in loc
        assert '\\' in loc


class TestStandardDir:

    """Tests for standarddir."""

    @pytest.mark.parametrize('func, varname', [
        (standarddir.data, 'XDG_DATA_HOME'),
        (standarddir.config, 'XDG_CONFIG_HOME'),
        (lambda: standarddir.config(auto=True), 'XDG_CONFIG_HOME'),
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
        standarddir._init_dirs()
        assert func() == str(tmpdir / 'qute_test')

    @pytest.mark.parametrize('func, subdirs', [
        (standarddir.data, ['.local', 'share', 'qute_test']),
        (standarddir.config, ['.config', 'qute_test']),
        (lambda: standarddir.config(auto=True), ['.config', 'qute_test']),
        (standarddir.cache, ['.cache', 'qute_test']),
        (standarddir.download, ['Downloads']),
    ])
    @pytest.mark.linux
    def test_linux_normal(self, monkeypatch, tmpdir, func, subdirs):
        """Test dirs with XDG_*_HOME not set."""
        monkeypatch.setenv('HOME', str(tmpdir))
        for var in ['DATA', 'CONFIG', 'CACHE']:
            monkeypatch.delenv('XDG_{}_HOME'.format(var), raising=False)
        standarddir._init_dirs()
        assert func() == str(tmpdir.join(*subdirs))

    @pytest.mark.linux
    @pytest.mark.qt_log_ignore(r'^QStandardPaths: ')
    def test_linux_invalid_runtimedir(self, monkeypatch, tmpdir):
        """With invalid XDG_RUNTIME_DIR, fall back to TempLocation."""
        monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmpdir / 'does-not-exist'))
        monkeypatch.setenv('TMPDIR', str(tmpdir / 'temp'))
        standarddir._init_dirs()
        assert standarddir.runtime() == str(tmpdir / 'temp' / 'qute_test')

    def test_runtimedir_empty_tempdir(self, monkeypatch, tmpdir):
        """With an empty tempdir on non-Linux, we should raise."""
        monkeypatch.setattr(standarddir.sys, 'platform', 'nt')
        monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                            lambda typ: '')
        with pytest.raises(standarddir.EmptyValueError):
            standarddir._init_runtime(args=None)

    @pytest.mark.parametrize('func, elems, expected', [
        (standarddir.data, 2, ['qute_test', 'data']),
        (standarddir.config, 2, ['qute_test', 'config']),
        (lambda: standarddir.config(auto=True), 2, ['qute_test', 'config']),
        (standarddir.cache, 2, ['qute_test', 'cache']),
        (standarddir.download, 1, ['Downloads']),
    ])
    @pytest.mark.windows
    def test_windows(self, func, elems, expected):
        standarddir._init_dirs()
        assert func().split(os.sep)[-elems:] == expected

    @pytest.mark.parametrize('func, elems, expected', [
        (standarddir.data, 2, ['Application Support', 'qute_test']),
        (lambda: standarddir.config(auto=True), 1, ['qute_test']),
        (standarddir.config, 0,
         os.path.expanduser('~').split(os.sep) + ['.qutebrowser']),
        (standarddir.cache, 2, ['Caches', 'qute_test']),
        (standarddir.download, 1, ['Downloads']),
    ])
    @pytest.mark.mac
    def test_mac(self, func, elems, expected):
        standarddir._init_dirs()
        assert func().split(os.sep)[-elems:] == expected


DirArgTest = collections.namedtuple('DirArgTest', 'arg, expected')


class TestArguments:

    """Tests the --basedir argument."""

    @pytest.mark.parametrize('typ, args', [
        ('config', []),
        ('config', [True]),  # user config
        ('data', []),
        ('cache', []),
        ('download', []),
        pytest.param('runtime', [], marks=pytest.mark.linux)])
    def test_basedir(self, tmpdir, typ, args):
        """Test --basedir."""
        expected = str(tmpdir / typ)
        init_args = types.SimpleNamespace(basedir=str(tmpdir))
        standarddir._init_dirs(init_args)
        func = getattr(standarddir, typ)
        assert func(*args) == expected

    def test_basedir_relative(self, tmpdir):
        """Test --basedir with a relative path."""
        basedir = (tmpdir / 'basedir')
        basedir.ensure(dir=True)
        with tmpdir.as_cwd():
            args = types.SimpleNamespace(basedir='basedir')
            standarddir._init_dirs(args)
            assert standarddir.config() == str(basedir / 'config')


class TestInitCacheDirTag:

    """Tests for _init_cachedir_tag."""

    def test_existent_cache_dir_tag(self, tmpdir, mocker, monkeypatch):
        """Test with an existent CACHEDIR.TAG."""
        monkeypatch.setattr(standarddir, 'cache', lambda: str(tmpdir))
        mocker.patch('builtins.open', side_effect=AssertionError)
        m = mocker.patch('qutebrowser.utils.standarddir.os')
        m.path.join.side_effect = os.path.join
        m.path.exists.return_value = True
        standarddir._init_cachedir_tag()
        assert not tmpdir.listdir()
        m.path.exists.assert_called_with(str(tmpdir / 'CACHEDIR.TAG'))

    def test_new_cache_dir_tag(self, tmpdir, mocker, monkeypatch):
        """Test creating a new CACHEDIR.TAG."""
        monkeypatch.setattr(standarddir, 'cache', lambda: str(tmpdir))
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
        monkeypatch.setattr(standarddir, 'cache', lambda: str(tmpdir))
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
        standarddir._init_dirs(args)

        func = getattr(standarddir, typ)
        func()

        assert basedir.exists()

        if os.name == 'posix':
            assert basedir.stat().mode & 0o777 == 0o700

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
        m.expanduser = os.path.expanduser
        m.path.exists.return_value = False
        m.path.abspath = lambda x: x

        args = types.SimpleNamespace(basedir=str(tmpdir))
        standarddir._init_dirs(args)

        func = getattr(standarddir, typ)
        func()


class TestSystemData:

    """Test system data path."""

    def test_system_datadir_exist_linux(self, monkeypatch):
        """Test that /usr/share/qutebrowser is used if path exists."""
        monkeypatch.setattr('sys.platform', "linux")
        monkeypatch.setattr(os.path, 'exists', lambda path: True)
        standarddir._init_dirs()
        assert standarddir.data(system=True) == "/usr/share/qutebrowser"

    @pytest.mark.linux
    def test_system_datadir_not_exist_linux(self, monkeypatch, tmpdir,
                                            fake_args):
        """Test that system-wide path isn't used on linux if path not exist."""
        fake_args.basedir = str(tmpdir)
        monkeypatch.setattr(os.path, 'exists', lambda path: False)
        standarddir._init_dirs(fake_args)
        assert standarddir.data(system=True) == standarddir.data()

    def test_system_datadir_unsupportedos(self, monkeypatch, tmpdir,
                                          fake_args):
        """Test that system-wide path is not used on non-Linux OS."""
        fake_args.basedir = str(tmpdir)
        monkeypatch.setattr('sys.platform', "potato")
        standarddir._init_dirs(fake_args)
        assert standarddir.data(system=True) == standarddir.data()


# FIXME:conf needs AppDataLocation
@pytest.mark.qt55
class TestDataMigrations:

    """Test moving various data from an old to a new location."""

    @pytest.fixture(autouse=True)
    def patch_standardpaths(self, files, tmpdir, monkeypatch):
        locations = {
            QStandardPaths.DataLocation: str(files.local_data_dir),
            QStandardPaths.CacheLocation: str(tmpdir / 'cache'),
            QStandardPaths.AppDataLocation: str(files.roaming_data_dir),
        }
        monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                            locations.get)

        monkeypatch.setattr(standarddir, 'data',
                            lambda: str(tmpdir / 'new_data'))
        monkeypatch.setattr(standarddir, 'cache',
                            lambda: str(tmpdir / 'new_cache'))
        monkeypatch.setattr(
            standarddir, 'config', lambda auto=False:
            str(files.auto_config_dir if auto else files.config_dir))

    @pytest.fixture
    def files(self, tmpdir):
        files = collections.namedtuple('Files', [
            'old_webengine_data', 'new_webengine_data',
            'old_webengine_cache', 'new_webengine_cache',
            'auto_config_dir', 'config_dir',
            'local_data_dir', 'roaming_data_dir'])
        return files(
            old_webengine_data=(tmpdir / 'data' / 'QtWebEngine' / 'Default' /
                                'datafile'),
            new_webengine_data=tmpdir / 'new_data' / 'webengine' / 'datafile',
            old_webengine_cache=(tmpdir / 'cache' / 'QtWebEngine' / 'Default' /
                                 'cachefile'),
            new_webengine_cache=(tmpdir / 'new_cache' / 'webengine' /
                                 'cachefile'),
            auto_config_dir=tmpdir / 'auto_config',
            config_dir=tmpdir / 'config',
            local_data_dir=tmpdir / 'data',
            roaming_data_dir=tmpdir / 'roaming-data',
        )

    def test_no_webengine_dir(self, caplog):
        """Nothing should happen without any QtWebEngine directory."""
        standarddir._move_webengine_data()
        assert not any(rec.message.startswith('Moving QtWebEngine')
                       for rec in caplog.records)

    def test_moving_data(self, files):
        files.old_webengine_data.ensure()
        files.old_webengine_cache.ensure()

        standarddir._move_webengine_data()

        assert not files.old_webengine_data.exists()
        assert not files.old_webengine_cache.exists()
        assert files.new_webengine_data.exists()
        assert files.new_webengine_cache.exists()

    @pytest.mark.parametrize('what', ['data', 'cache'])
    def test_already_existing(self, files, caplog, what):
        files.old_webengine_data.ensure()
        files.old_webengine_cache.ensure()

        if what == 'data':
            files.new_webengine_data.ensure()
            old_path = str(files.old_webengine_data.dirname)
            new_path = str(files.new_webengine_data.dirname)
        else:
            files.new_webengine_cache.ensure()
            old_path = str(files.old_webengine_cache.dirname)
            new_path = str(files.new_webengine_cache.dirname)

        with caplog.at_level(logging.ERROR):
            standarddir._move_webengine_data()

        record = caplog.records[-1]
        expected = "Failed to move data from {} as {} is non-empty!".format(
            old_path, new_path)
        assert record.message == expected

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
        files.old_webengine_data.ensure()
        files.old_webengine_cache.ensure()

        with caplog.at_level(logging.ERROR):
            standarddir._move_webengine_data()

        record = caplog.records[-1]
        expected = "Failed to move data from {} to {}: error".format(
            files.old_webengine_data.dirname, files.new_webengine_data.dirname)
        assert record.message == expected

    def test_existing_but_empty(self, tmpdir):
        """Make sure moving works with an empty destination dir."""
        old_dir = tmpdir / 'old' / 'foo'
        new_dir = tmpdir / 'new' / 'foo'
        old_file = old_dir / 'file'
        new_file = new_dir / 'file'
        old_file.ensure()
        new_dir.ensure(dir=True)

        standarddir._move_data(str(old_dir), str(new_dir))
        assert not old_file.exists()
        assert new_file.exists()

    def test_move_macos(self, files):
        """Test moving configs on macOS."""
        (files.auto_config_dir / 'autoconfig.yml').ensure()
        (files.auto_config_dir / 'quickmarks').ensure()
        files.config_dir.ensure(dir=True)

        standarddir._move_macos()

        assert (files.auto_config_dir / 'autoconfig.yml').exists()
        assert not (files.config_dir / 'autoconfig.yml').exists()
        assert not (files.auto_config_dir / 'quickmarks').exists()
        assert (files.config_dir / 'quickmarks').exists()

    def test_move_windows(self, files):
        """Test moving configs on Windows."""
        (files.local_data_dir / 'data' / 'blocked-hosts').ensure()
        (files.local_data_dir / 'qutebrowser.conf').ensure()
        (files.local_data_dir / 'cache' / 'cachefile').ensure()

        standarddir._move_windows()

        assert (files.roaming_data_dir / 'data' / 'blocked-hosts').exists()
        assert (files.roaming_data_dir / 'config' /
                'qutebrowser.conf').exists()
        assert not (files.roaming_data_dir / 'cache').exists()
        assert (files.local_data_dir / 'cache' / 'cachefile').exists()


@pytest.mark.parametrize('args_kind', ['basedir', 'normal', 'none'])
def test_init(mocker, tmpdir, args_kind):
    """Do some sanity checks for standarddir.init().

    Things like _init_cachedir_tag() and _move_webengine_data() are tested in
    more detail in other tests.
    """
    assert standarddir._locations == {}

    m = mocker.patch('qutebrowser.utils.standarddir._move_webengine_data')
    m_windows = mocker.patch('qutebrowser.utils.standarddir._move_windows')
    m_mac = mocker.patch('qutebrowser.utils.standarddir._move_macos')
    if args_kind == 'normal':
        args = types.SimpleNamespace(basedir=None)
    elif args_kind == 'basedir':
        args = types.SimpleNamespace(basedir=str(tmpdir))
    else:
        assert args_kind == 'none'
        args = None

    standarddir.init(args)

    assert standarddir._locations != {}
    if args_kind == 'normal':
        assert m.called
        if sys.platform == 'darwin':
            assert not m_windows.called
            assert m_mac.called
        elif os.name == 'nt':
            assert m_windows.called
            assert not m_mac.called
        else:
            assert not m_windows.called
            assert not m_mac.called
    else:
        assert not m.called
        assert not m_windows.called
        assert not m_mac.called


@pytest.mark.linux
def test_downloads_dir_not_crated(monkeypatch, tmpdir):
    """Make sure ~/Downloads is not created."""
    download_dir = tmpdir / 'Downloads'
    monkeypatch.setenv('HOME', str(tmpdir))
    # Make sure xdg-user-dirs.dirs is not picked up
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    standarddir._init_dirs()
    assert standarddir.download() == str(download_dir)
    assert not download_dir.exists()
