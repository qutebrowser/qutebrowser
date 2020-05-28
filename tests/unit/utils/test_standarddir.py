# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import sys
import json
import types
import textwrap
import logging
import subprocess

import attr
from PyQt5.QtCore import QStandardPaths
import pytest

from qutebrowser.utils import standarddir, utils, qtutils


# Use a different application name for tests to make sure we don't change real
# qutebrowser data if we accidentally access the real path in a test.
APPNAME = 'qute_test'


pytestmark = pytest.mark.usefixtures('qapp')


@pytest.fixture(autouse=True)
def clear_standarddir_cache_and_patch(qapp, monkeypatch):
    """Make sure the standarddir cache is cleared before/after each test.

    Also, patch APPNAME to qute_test.
    """
    assert qapp.applicationName() == APPNAME
    monkeypatch.setattr(standarddir, '_locations', {})
    monkeypatch.setattr(standarddir, 'APPNAME', APPNAME)
    yield
    monkeypatch.setattr(standarddir, '_locations', {})


@pytest.mark.parametrize('orgname, expected', [(None, ''), ('test', 'test')])
def test_unset_organization(qapp, orgname, expected):
    """Test unset_organization.

    Args:
        orgname: The organizationName to set initially.
        expected: The organizationName which is expected when reading back.
    """
    qapp.setOrganizationName(orgname)
    assert qapp.organizationName() == expected  # sanity check
    with standarddir._unset_organization():
        assert qapp.organizationName() == ''
    assert qapp.organizationName() == expected


def test_unset_organization_no_qapp(monkeypatch):
    """Without a QApplication, _unset_organization should do nothing."""
    monkeypatch.setattr(standarddir.QApplication, 'instance', lambda: None)
    with standarddir._unset_organization():
        pass


@pytest.mark.fake_os('mac')
def test_fake_mac_config(tmpdir, monkeypatch):
    """Test standardir.config on a fake Mac."""
    monkeypatch.setenv('HOME', str(tmpdir))
    expected = str(tmpdir) + '/.qute_test'  # always with /
    standarddir._init_config(args=None)
    assert standarddir.config() == expected


@pytest.mark.parametrize('what', ['data', 'config', 'cache'])
@pytest.mark.not_mac
@pytest.mark.fake_os('windows')
def test_fake_windows(tmpdir, monkeypatch, what):
    """Make sure the config/data/cache dirs are correct on a fake Windows."""
    monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                        lambda typ: str(tmpdir / APPNAME))

    standarddir._init_config(args=None)
    standarddir._init_data(args=None)
    standarddir._init_cache(args=None)

    func = getattr(standarddir, what)
    assert func() == str(tmpdir / APPNAME / what)


@pytest.mark.posix
def test_fake_haiku(tmpdir, monkeypatch):
    """Test getting data dir on HaikuOS."""
    locations = {
        QStandardPaths.DataLocation: '',
        QStandardPaths.ConfigLocation: str(tmpdir / 'config' / APPNAME),
    }
    monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                        locations.get)
    monkeypatch.setattr(standarddir.sys, 'platform', 'haiku1')

    standarddir._init_data(args=None)
    assert standarddir.data() == str(tmpdir / 'config' / APPNAME / 'data')


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
        monkeypatch.setattr(standarddir.os.path, 'join',
                            lambda *parts: '\\'.join(parts))
        loc = standarddir._writable_location(QStandardPaths.DataLocation)
        assert '/' not in loc
        assert '\\' in loc


class TestStandardDir:

    @pytest.mark.parametrize('func, init_func, varname', [
        (standarddir.data, standarddir._init_data, 'XDG_DATA_HOME'),
        (standarddir.config, standarddir._init_config, 'XDG_CONFIG_HOME'),
        (lambda: standarddir.config(auto=True),
         standarddir._init_config, 'XDG_CONFIG_HOME'),
        (standarddir.cache, standarddir._init_cache, 'XDG_CACHE_HOME'),
        (standarddir.runtime, standarddir._init_runtime, 'XDG_RUNTIME_DIR'),
    ])
    @pytest.mark.linux
    def test_linux_explicit(self, monkeypatch, tmpdir,
                            func, init_func, varname):
        """Test dirs with XDG environment variables explicitly set.

        Args:
            func: The function to test.
            init_func: The initialization function to call.
            varname: The environment variable which should be set.
        """
        monkeypatch.setenv(varname, str(tmpdir))
        if varname == 'XDG_RUNTIME_DIR':
            tmpdir.chmod(0o0700)

        init_func(args=None)
        assert func() == str(tmpdir / APPNAME)

    @pytest.mark.parametrize('func, subdirs', [
        (standarddir.data, ['.local', 'share', APPNAME]),
        (standarddir.config, ['.config', APPNAME]),
        (lambda: standarddir.config(auto=True), ['.config', APPNAME]),
        (standarddir.cache, ['.cache', APPNAME]),
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
    @pytest.mark.skipif(
        qtutils.version_check('5.14', compiled=False),
        reason="Qt 5.14 automatically creates missing runtime dirs")
    def test_linux_invalid_runtimedir(self, monkeypatch, tmpdir):
        """With invalid XDG_RUNTIME_DIR, fall back to TempLocation."""
        tmpdir_env = tmpdir / 'temp'
        tmpdir_env.ensure(dir=True)
        monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmpdir / 'does-not-exist'))
        monkeypatch.setenv('TMPDIR', str(tmpdir_env))

        standarddir._init_runtime(args=None)
        assert standarddir.runtime() == str(tmpdir_env / APPNAME)

    @pytest.mark.fake_os('windows')
    def test_runtimedir_empty_tempdir(self, monkeypatch, tmpdir):
        """With an empty tempdir on non-Linux, we should raise."""
        monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                            lambda typ: '')
        with pytest.raises(standarddir.EmptyValueError):
            standarddir._init_runtime(args=None)

    @pytest.mark.parametrize('func, elems, expected', [
        (standarddir.data, 2, [APPNAME, 'data']),
        (standarddir.config, 2, [APPNAME, 'config']),
        (lambda: standarddir.config(auto=True), 2, [APPNAME, 'config']),
        (standarddir.cache, 2, [APPNAME, 'cache']),
        (standarddir.download, 1, ['Downloads']),
    ])
    @pytest.mark.windows
    def test_windows(self, func, elems, expected):
        standarddir._init_dirs()
        assert func().split(os.sep)[-elems:] == expected

    @pytest.mark.parametrize('func, elems, expected', [
        (standarddir.data, 2, ['Application Support', APPNAME]),
        (lambda: standarddir.config(auto=True), 1, [APPNAME]),
        (standarddir.config, 0,
         os.path.expanduser('~').split(os.sep) + ['.qute_test']),
        (standarddir.cache, 2, ['Caches', APPNAME]),
        (standarddir.download, 1, ['Downloads']),
    ])
    @pytest.mark.mac
    def test_mac(self, func, elems, expected):
        standarddir._init_dirs()
        assert func().split(os.sep)[-elems:] == expected


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

    def test_config_py_arg(self, tmpdir):
        basedir = tmpdir / 'basedir'
        basedir.ensure(dir=True)
        with tmpdir.as_cwd():
            args = types.SimpleNamespace(
                basedir='foo', config_py='basedir/config.py')
            standarddir._init_dirs(args)
            assert standarddir.config_py() == str(basedir / 'config.py')

    def test_config_py_no_arg(self, tmpdir):
        basedir = tmpdir / 'basedir'
        basedir.ensure(dir=True)
        with tmpdir.as_cwd():
            args = types.SimpleNamespace(basedir='basedir')
            standarddir._init_dirs(args)
            assert standarddir.config_py() == str(
                basedir / 'config' / 'config.py')


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
        assert caplog.messages == ['Failed to create CACHEDIR.TAG']
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

        if typ == 'download' or (typ == 'runtime' and not utils.is_linux):
            assert not (basedir / typ).exists()
        else:
            assert (basedir / typ).exists()

            if utils.is_posix:
                assert (basedir / typ).stat().mode & 0o777 == 0o700

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

    @pytest.mark.linux
    def test_system_datadir_exist_linux(self, monkeypatch, tmpdir):
        """Test that /usr/share/qute_test is used if path exists."""
        monkeypatch.setenv('XDG_DATA_HOME', str(tmpdir))
        monkeypatch.setattr(os.path, 'exists', lambda path: True)
        standarddir._init_data(args=None)
        assert standarddir.data(system=True) == "/usr/share/qute_test"

    @pytest.mark.linux
    def test_system_datadir_not_exist_linux(self, monkeypatch, tmpdir,
                                            fake_args):
        """Test that system-wide path isn't used on linux if path not exist."""
        fake_args.basedir = str(tmpdir)
        monkeypatch.setattr(os.path, 'exists', lambda path: False)
        standarddir._init_data(args=fake_args)
        assert standarddir.data(system=True) == standarddir.data()

    def test_system_datadir_unsupportedos(self, monkeypatch, tmpdir,
                                          fake_args):
        """Test that system-wide path is not used on non-Linux OS."""
        fake_args.basedir = str(tmpdir)
        monkeypatch.setattr('sys.platform', "potato")
        standarddir._init_data(args=fake_args)
        assert standarddir.data(system=True) == standarddir.data()


class TestMoveWindowsAndMacOS:

    """Test other invocations of _move_data."""

    @pytest.fixture(autouse=True)
    def patch_standardpaths(self, files, monkeypatch):
        locations = {
            QStandardPaths.DataLocation: str(files.local_data_dir),
            QStandardPaths.AppDataLocation: str(files.roaming_data_dir),
        }
        monkeypatch.setattr(standarddir.QStandardPaths, 'writableLocation',
                            locations.get)
        monkeypatch.setattr(
            standarddir, 'config', lambda auto=False:
            str(files.auto_config_dir if auto else files.config_dir))

    @pytest.fixture
    def files(self, tmpdir):

        @attr.s
        class Files:

            auto_config_dir = attr.ib()
            config_dir = attr.ib()
            local_data_dir = attr.ib()
            roaming_data_dir = attr.ib()

        return Files(
            auto_config_dir=tmpdir / 'auto_config' / APPNAME,
            config_dir=tmpdir / 'config' / APPNAME,
            local_data_dir=tmpdir / 'data' / APPNAME,
            roaming_data_dir=tmpdir / 'roaming-data' / APPNAME,
        )

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


class TestMove:

    @pytest.fixture
    def dirs(self, tmpdir):
        @attr.s
        class Dirs:

            old = attr.ib()
            new = attr.ib()
            old_file = attr.ib()
            new_file = attr.ib()

        old_dir = tmpdir / 'old'
        new_dir = tmpdir / 'new'
        return Dirs(old=old_dir, new=new_dir,
                    old_file=old_dir / 'file', new_file=new_dir / 'file')

    def test_no_old_dir(self, dirs, caplog):
        """Nothing should happen without any old directory."""
        standarddir._move_data(str(dirs.old), str(dirs.new))
        assert not any(message.startswith('Migrating data from')
                       for message in caplog.messages)

    @pytest.mark.parametrize('empty_dest', [True, False])
    def test_moving_data(self, dirs, empty_dest):
        dirs.old_file.ensure()
        if empty_dest:
            dirs.new.ensure(dir=True)

        standarddir._move_data(str(dirs.old), str(dirs.new))
        assert not dirs.old_file.exists()
        assert dirs.new_file.exists()

    def test_already_existing(self, dirs, caplog):
        dirs.old_file.ensure()
        dirs.new_file.ensure()

        with caplog.at_level(logging.ERROR):
            standarddir._move_data(str(dirs.old), str(dirs.new))

        expected = "Failed to move data from {} as {} is non-empty!".format(
            dirs.old, dirs.new)
        assert caplog.messages[-1] == expected

    def test_deleting_error(self, dirs, monkeypatch, mocker, caplog):
        """When there was an error it should be logged."""
        mock = mocker.Mock(side_effect=OSError('error'))
        monkeypatch.setattr(standarddir.shutil, 'move', mock)
        dirs.old_file.ensure()

        with caplog.at_level(logging.ERROR):
            standarddir._move_data(str(dirs.old), str(dirs.new))

        expected = "Failed to move data from {} to {}: error".format(
            dirs.old, dirs.new)
        assert caplog.messages[-1] == expected


@pytest.mark.parametrize('args_kind', ['basedir', 'normal', 'none'])
def test_init(mocker, tmpdir, monkeypatch, args_kind):
    """Do some sanity checks for standarddir.init().

    Things like _init_cachedir_tag() are tested in more detail in other tests.
    """
    assert standarddir._locations == {}

    monkeypatch.setenv('HOME', str(tmpdir))

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
        if utils.is_mac:
            m_windows.assert_not_called()
            assert m_mac.called
        elif utils.is_windows:
            assert m_windows.called
            m_mac.assert_not_called()
        else:
            m_windows.assert_not_called()
            m_mac.assert_not_called()
    else:
        m_windows.assert_not_called()
        m_mac.assert_not_called()


@pytest.mark.linux
def test_downloads_dir_not_created(monkeypatch, tmpdir):
    """Make sure ~/Downloads is not created."""
    download_dir = tmpdir / 'Downloads'
    monkeypatch.setenv('HOME', str(tmpdir))
    # Make sure xdg-user-dirs.dirs is not picked up
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    standarddir._init_dirs()
    assert standarddir.download() == str(download_dir)
    assert not download_dir.exists()


def test_no_qapplication(qapp, tmpdir, monkeypatch):
    """Make sure directories with/without QApplication are equal."""
    sub_code = """
        import sys
        import json

        sys.path = sys.argv[1:]  # make sure we have the same python path

        from PyQt5.QtWidgets import QApplication
        from qutebrowser.utils import standarddir

        assert QApplication.instance() is None

        standarddir.APPNAME = 'qute_test'
        standarddir._init_dirs()

        locations = {k.name: v for k, v in standarddir._locations.items()}
        print(json.dumps(locations))
    """
    pyfile = tmpdir / 'sub.py'
    pyfile.write_text(textwrap.dedent(sub_code), encoding='ascii')

    for name in ['CONFIG', 'DATA', 'CACHE']:
        monkeypatch.delenv('XDG_{}_HOME'.format(name), raising=False)

    runtime_dir = tmpdir / 'runtime'
    runtime_dir.ensure(dir=True)
    runtime_dir.chmod(0o0700)
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(runtime_dir))

    home_dir = tmpdir / 'home'
    home_dir.ensure(dir=True)
    monkeypatch.setenv('HOME', str(home_dir))

    proc = subprocess.run([sys.executable, str(pyfile)] + sys.path,
                          universal_newlines=True,
                          check=True,
                          stdout=subprocess.PIPE)
    sub_locations = json.loads(proc.stdout)

    standarddir._init_dirs()
    locations = {k.name: v for k, v in standarddir._locations.items()}

    assert sub_locations == locations
