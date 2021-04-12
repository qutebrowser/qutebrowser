# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.utils.version."""

import io
import sys
import os
import pathlib
import subprocess
import contextlib
import logging
import textwrap
import datetime
import dataclasses

import pytest
import hypothesis
import hypothesis.strategies
from PyQt5.QtCore import PYQT_VERSION_STR

import qutebrowser
from qutebrowser.config import config, websettings
from qutebrowser.utils import version, usertypes, utils, standarddir
from qutebrowser.misc import pastebin, objects, elf
from qutebrowser.browser import pdfjs

try:
    from qutebrowser.browser.webengine import webenginesettings
except ImportError:
    webenginesettings = None


@pytest.mark.parametrize('os_release, expected', [
    # No file
    (None, None),
    # Invalid file
    ("\n# foo\n foo=bar=baz",
     version.DistributionInfo(id=None, parsed=version.Distribution.unknown,
                              pretty='Unknown')),
    # Archlinux
    ("""
        NAME="Arch Linux"
        PRETTY_NAME="Arch Linux"
        ID=arch
        ID_LIKE=archlinux
        ANSI_COLOR="0;36"
        HOME_URL="https://www.archlinux.org/"
        SUPPORT_URL="https://bbs.archlinux.org/"
        BUG_REPORT_URL="https://bugs.archlinux.org/"
     """,
     version.DistributionInfo(
         id='arch', parsed=version.Distribution.arch, pretty='Arch Linux')),
    # Ubuntu 14.04
    ("""
        NAME="Ubuntu"
        VERSION="14.04.5 LTS, Trusty Tahr"
        ID=ubuntu
        ID_LIKE=debian
        PRETTY_NAME="Ubuntu 14.04.5 LTS"
        VERSION_ID="14.04"
     """,
     version.DistributionInfo(
         id='ubuntu', parsed=version.Distribution.ubuntu, pretty='Ubuntu 14.04.5 LTS')),
    # Ubuntu 17.04
    ("""
        NAME="Ubuntu"
        VERSION="17.04 (Zesty Zapus)"
        ID=ubuntu
        ID_LIKE=debian
        PRETTY_NAME="Ubuntu 17.04"
        VERSION_ID="17.04"
     """,
     version.DistributionInfo(
         id='ubuntu', parsed=version.Distribution.ubuntu, pretty='Ubuntu 17.04')),
    # Debian Jessie
    ("""
        PRETTY_NAME="Debian GNU/Linux 8 (jessie)"
        NAME="Debian GNU/Linux"
        VERSION_ID="8"
        VERSION="8 (jessie)"
        ID=debian
     """,
     version.DistributionInfo(
         id='debian', parsed=version.Distribution.debian,
         pretty='Debian GNU/Linux 8 (jessie)')),
    # Void Linux
    ("""
        NAME="void"
        ID="void"
        DISTRIB_ID="void"
        PRETTY_NAME="void"
     """,
     version.DistributionInfo(
         id='void', parsed=version.Distribution.void, pretty='void')),
    # Gentoo
    ("""
        NAME=Gentoo
        ID=gentoo
        PRETTY_NAME="Gentoo/Linux"
     """,
     version.DistributionInfo(
         id='gentoo', parsed=version.Distribution.gentoo, pretty='Gentoo/Linux')),
    # Fedora
    ("""
        NAME=Fedora
        VERSION="25 (Twenty Five)"
        ID=fedora
        VERSION_ID=25
        PRETTY_NAME="Fedora 25 (Twenty Five)"
     """,
     version.DistributionInfo(
         id='fedora', parsed=version.Distribution.fedora,
         pretty='Fedora 25 (Twenty Five)')),
    # OpenSUSE
    ("""
        NAME="openSUSE Leap"
        VERSION="42.2"
        ID=opensuse
        ID_LIKE="suse"
        VERSION_ID="42.2"
        PRETTY_NAME="openSUSE Leap 42.2"
     """,
     version.DistributionInfo(
         id='opensuse', parsed=version.Distribution.opensuse,
         pretty='openSUSE Leap 42.2')),
    # Linux Mint
    ("""
        NAME="Linux Mint"
        VERSION="18.1 (Serena)"
        ID=linuxmint
        ID_LIKE=ubuntu
        PRETTY_NAME="Linux Mint 18.1"
        VERSION_ID="18.1"
     """,
     version.DistributionInfo(
         id='linuxmint', parsed=version.Distribution.linuxmint,
         pretty='Linux Mint 18.1')),
    # Manjaro
    ("""
        NAME="Manjaro Linux"
        ID=manjaro
        PRETTY_NAME="Manjaro Linux"
     """,
     version.DistributionInfo(
         id='manjaro', parsed=version.Distribution.manjaro, pretty='Manjaro Linux')),
    # Funtoo
    ("""
        ID="funtoo"
        NAME="Funtoo GNU/Linux"
        PRETTY_NAME="Linux"
     """,
     version.DistributionInfo(
         id='funtoo', parsed=version.Distribution.gentoo, pretty='Funtoo GNU/Linux')),
    # KDE neon
    ("""
        NAME="KDE neon"
        VERSION="5.20"
        ID=neon
        ID_LIKE="ubuntu debian"
        PRETTY_NAME="KDE neon User Edition 5.20"
        VARIANT="User Edition"
        VERSION_ID="20.04"
    """,
    version.DistributionInfo(
        id='neon', parsed=version.Distribution.neon,
        pretty='KDE neon User Edition 5.20')),
    # Archlinux ARM
    ("""
        NAME="Arch Linux ARM"
        PRETTY_NAME="Arch Linux ARM"
        ID=archarm
        ID_LIKE=arch
    """,
    version.DistributionInfo(
        id='archarm', parsed=version.Distribution.arch, pretty='Arch Linux ARM')),
    # Alpine
    ("""
        NAME="Alpine Linux"
        ID=alpine
        VERSION_ID=3.12_alpha20200122
        PRETTY_NAME="Alpine Linux edge"
    """,
    version.DistributionInfo(
        id='alpine', parsed=version.Distribution.alpine, pretty='Alpine Linux edge')),
    # EndeavourOS
    ("""
        NAME="EndeavourOS"
        PRETTY_NAME="EndeavourOS"
        ID=endeavouros
        ID_LIKE=arch
        BUILD_ID=rolling
        DOCUMENTATION_URL="https://endeavouros.com/wiki/"
        LOGO=endeavouros
    """,
    version.DistributionInfo(
        id='endeavouros', parsed=version.Distribution.arch, pretty='EndeavourOS')),
    # Manjaro ARM
    ("""
        NAME="Manjaro-ARM"
        ID=manjaro-arm
        ID_LIKE=manjaro arch
        PRETTY_NAME="Manjaro ARM"
    """,
    version.DistributionInfo(
        id='manjaro-arm', parsed=version.Distribution.manjaro, pretty='Manjaro ARM')),
    # Artix Linux
    ("""
        NAME="Artix Linux"
        PRETTY_NAME="Artix Linux"
        ID=artix
    """,
    version.DistributionInfo(
        id='artix', parsed=version.Distribution.arch, pretty='Artix Linux')),
    # NixOS
    ("""
        NAME=NixOS
        ID=nixos
        VERSION="21.03pre268206.536fe36e23a (Okapi)"
        VERSION_CODENAME=okapi
        VERSION_ID="21.03pre268206.536fe36e23a"
        PRETTY_NAME="NixOS 21.03 (Okapi)"
    """,
    version.DistributionInfo(
        id='nixos', parsed=version.Distribution.nixos, pretty='NixOS 21.03 (Okapi)')),
    # NixOS (fake fourth version component)
    ("""
        NAME=NixOS
        ID=nixos
        VERSION="21.05.20210402.1dead (Okapi)"
    """,
    version.DistributionInfo(
        id='nixos', parsed=version.Distribution.nixos, pretty='NixOS')),
    # SolusOS
    ("""
        NAME="Solus"
        VERSION="4.2"
        ID="solus"
        VERSION_CODENAME=fortitude
        VERSION_ID="4.2"
        PRETTY_NAME="Solus 4.2 Fortitude"
    """,
    version.DistributionInfo(
        id='solus', parsed=version.Distribution.solus, pretty='Solus 4.2 Fortitude')),
    # KDE Platform
    ("""
        NAME=KDE
        VERSION="5.12 (Flatpak runtime)"
        VERSION_ID="5.12"
        ID=org.kde.Platform
    """,
    version.DistributionInfo(
        id='org.kde.Platform', parsed=version.Distribution.kde_flatpak, pretty='KDE')),
    # No PRETTY_NAME
    ("""
        NAME="Tux"
        ID=tux
    """,
    version.DistributionInfo(
        id='tux', parsed=version.Distribution.unknown, pretty='Tux')),
    # Invalid multi-line value
    ("""
        ID=tux
        PRETTY_NAME="Multiline
        Text"
    """,
    version.DistributionInfo(
        id='tux', parsed=version.Distribution.unknown, pretty='Multiline')),
])
def test_distribution(tmp_path, monkeypatch, os_release, expected):
    os_release_file = tmp_path / 'os-release'
    if os_release is not None:
        os_release_file.write_text(textwrap.dedent(os_release), encoding="utf-8")
    monkeypatch.setenv('QUTE_FAKE_OS_RELEASE', str(os_release_file))

    assert version.distribution() == expected


@pytest.mark.parametrize('has_env', [True, False])
@pytest.mark.parametrize('has_file', [True, False])
def test_is_flatpak(monkeypatch, tmp_path, has_env, has_file):
    if has_env:
        monkeypatch.setenv('FLATPAK_ID', 'org.qutebrowser.qutebrowser')
    else:
        monkeypatch.delenv('FLATPAK_ID', raising=False)

    fake_info_path = tmp_path / '.flatpak_info'
    if has_file:
        lines = [
            "[Application]",
            "name=org.qutebrowser.qutebrowser",
            "runtime=runtime/org.kde.Platform/x86_64/5.15",
        ]
        fake_info_path.write_text('\n'.join(lines))
    else:
        assert not fake_info_path.exists()
    monkeypatch.setattr(version, '_FLATPAK_INFO_PATH', str(fake_info_path))

    assert version.is_flatpak() == (has_env or has_file)


class GitStrSubprocessFake:
    """Object returned by the git_str_subprocess_fake fixture.

    This provides a function which is used to patch _git_str_subprocess.

    Attributes:
        retval: The value to return when called. Needs to be set before func is
                called.
    """

    UNSET = object()

    def __init__(self):
        self.retval = self.UNSET

    def func(self, gitpath):
        """Function called instead of _git_str_subprocess.

        Checks whether the path passed is what we expected, and returns
        self.retval.
        """
        if self.retval is self.UNSET:
            raise ValueError("func got called without retval being set!")
        retval = self.retval
        self.retval = self.UNSET
        gitpath = pathlib.Path(gitpath).resolve()
        expected = pathlib.Path(qutebrowser.__file__).parent.parent
        assert gitpath == expected
        return retval


class TestGitStr:

    """Tests for _git_str()."""

    @pytest.fixture
    def commit_file_mock(self, mocker):
        """Fixture providing a mock for resources.read_file for git-commit-id.

        On fixture teardown, it makes sure it got called with git-commit-id as
        argument.
        """
        mocker.patch('qutebrowser.utils.version.subprocess',
                     side_effect=AssertionError)
        m = mocker.patch('qutebrowser.utils.version.resources.read_file')
        yield m
        m.assert_called_with('git-commit-id')

    @pytest.fixture
    def git_str_subprocess_fake(self, mocker, monkeypatch):
        """Fixture patching _git_str_subprocess with a GitStrSubprocessFake."""
        mocker.patch('qutebrowser.utils.version.subprocess',
                     side_effect=AssertionError)
        fake = GitStrSubprocessFake()
        monkeypatch.setattr(version, '_git_str_subprocess', fake.func)
        return fake

    def test_frozen_ok(self, commit_file_mock, monkeypatch):
        """Test with sys.frozen=True and a successful git-commit-id read."""
        monkeypatch.setattr(version.sys, 'frozen', True, raising=False)
        commit_file_mock.return_value = 'deadbeef'
        assert version._git_str() == 'deadbeef'

    def test_frozen_oserror(self, caplog, commit_file_mock, monkeypatch):
        """Test with sys.frozen=True and OSError when reading git-commit-id."""
        monkeypatch.setattr(version.sys, 'frozen', True, raising=False)
        commit_file_mock.side_effect = OSError
        with caplog.at_level(logging.ERROR, 'misc'):
            assert version._git_str() is None

    @pytest.mark.not_frozen
    def test_normal_successful(self, git_str_subprocess_fake):
        """Test with git returning a successful result."""
        git_str_subprocess_fake.retval = 'c0ffeebabe'
        assert version._git_str() == 'c0ffeebabe'

    @pytest.mark.frozen
    def test_normal_successful_frozen(self, git_str_subprocess_fake):
        """Test with git returning a successful result."""
        # The value is defined in scripts/freeze_tests.py.
        assert version._git_str() == 'fake-frozen-git-commit'

    def test_normal_error(self, commit_file_mock, git_str_subprocess_fake):
        """Test without repo (but git-commit-id)."""
        git_str_subprocess_fake.retval = None
        commit_file_mock.return_value = '1b4d1dea'
        assert version._git_str() == '1b4d1dea'

    def test_normal_path_oserror(self, mocker, git_str_subprocess_fake,
                                 caplog):
        """Test with things raising OSError."""
        m = mocker.patch('qutebrowser.utils.version.os')
        m.path.join.side_effect = OSError
        mocker.patch('qutebrowser.utils.version.resources.read_file',
                     side_effect=OSError)
        with caplog.at_level(logging.ERROR, 'misc'):
            assert version._git_str() is None

    @pytest.mark.not_frozen
    def test_normal_path_nofile(self, monkeypatch, caplog,
                                git_str_subprocess_fake, commit_file_mock):
        """Test with undefined __file__ but available git-commit-id."""
        monkeypatch.delattr(version, '__file__')
        commit_file_mock.return_value = '0deadcode'
        with caplog.at_level(logging.ERROR, 'misc'):
            assert version._git_str() == '0deadcode'
        assert caplog.messages == ["Error while getting git path"]


def _has_git():
    """Check if git is installed."""
    try:
        subprocess.run(['git', '--version'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    else:
        return True


# Decorator for tests needing git, so they get skipped when it's unavailable.
needs_git = pytest.mark.skipif(not _has_git(), reason='Needs git installed.')


class TestGitStrSubprocess:

    """Tests for _git_str_subprocess."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        """A fixture to create a temporary git repo.

        Some things are tested against a real repo so we notice if something in
        git would change, or we call git incorrectly.
        """
        def _git(*args):
            """Helper closure to call git."""
            env = os.environ.copy()
            env.update({
                'GIT_AUTHOR_NAME': 'qutebrowser testsuite',
                'GIT_AUTHOR_EMAIL': 'mail@qutebrowser.org',
                'GIT_AUTHOR_DATE': 'Thu  1 Jan 01:00:00 CET 1970',
                'GIT_COMMITTER_NAME': 'qutebrowser testsuite',
                'GIT_COMMITTER_EMAIL': 'mail@qutebrowser.org',
                'GIT_COMMITTER_DATE': 'Thu  1 Jan 01:00:00 CET 1970',
            })
            if utils.is_windows:
                # If we don't call this with shell=True it might fail under
                # some environments on Windows...
                # https://bugs.python.org/issue24493
                subprocess.run(
                    'git -C "{}" {}'.format(tmp_path, ' '.join(args)),
                    env=env, check=True, shell=True)
            else:
                subprocess.run(
                    ['git', '-C', str(tmp_path)] + list(args),
                    check=True, env=env)

        (tmp_path / 'file').write_text("Hello World!", encoding='utf-8')
        _git('init')
        _git('add', 'file')
        _git('commit', '-am', 'foo', '--no-verify', '--no-edit',
             '--no-post-rewrite', '--quiet', '--no-gpg-sign')
        _git('tag', 'foobar')
        return tmp_path

    @needs_git
    def test_real_git(self, git_repo):
        """Test with a real git repository."""
        ret = version._git_str_subprocess(str(git_repo))
        assert ret == '6e4b65a on master (1970-01-01 01:00:00 +0100)'

    def test_missing_dir(self, tmp_path):
        """Test with a directory which doesn't exist."""
        ret = version._git_str_subprocess(str(tmp_path / 'does-not-exist'))
        assert ret is None

    @pytest.mark.parametrize('exc', [
        OSError,
        subprocess.CalledProcessError(1, 'foobar')
    ])
    def test_exception(self, exc, mocker, tmp_path):
        """Test with subprocess.run raising an exception.

        Args:
            exc: The exception to raise.
        """
        m = mocker.patch('qutebrowser.utils.version.os')
        m.path.isdir.return_value = True
        mocker.patch('qutebrowser.utils.version.subprocess.run',
                     side_effect=exc)
        ret = version._git_str_subprocess(str(tmp_path))
        assert ret is None


class ReleaseInfoFake:

    """An object providing fakes for glob.glob/open for test_release_info.

    Attributes:
        _files: The files which should be returned, or None if an exception
        should be raised. A {filename: [lines]} dict.
    """

    def __init__(self, files):
        self._files = files

    def glob_fake(self, pattern):
        """Fake for glob.glob.

        Verifies the arguments and returns the files listed in self._files, or
        a single fake file if an exception is expected.
        """
        assert pattern == '/etc/*-release'
        if self._files is None:
            return ['fake-file']
        else:
            return sorted(self._files)

    @contextlib.contextmanager
    def open_fake(self, filename, mode, encoding):
        """Fake for open().

        Verifies the arguments and returns a StringIO with the content listed
        in self._files.
        """
        assert mode == 'r'
        assert encoding == 'utf-8'
        if self._files is None:
            raise OSError
        yield io.StringIO(''.join(self._files[filename]))


@pytest.mark.parametrize('files, expected', [
    # no files -> no output
    ({}, []),
    # empty files are stripped
    ({'file': ['']}, []),
    ({'file': []}, []),
    # newlines at EOL are stripped
    (
        {'file1': ['foo\n', 'bar\n'], 'file2': ['baz\n']},
        [('file1', 'foo\nbar'), ('file2', 'baz')]
    ),
    # blacklisted lines
    (
        {'file': ['HOME_URL=example.com\n', 'NAME=FOO']},
        [('file', 'NAME=FOO')]
    ),
    # only blacklisted lines
    ({'file': ['HOME_URL=example.com']}, []),
    # broken file
    (None, []),
])
def test_release_info(files, expected, caplog, monkeypatch):
    """Test _release_info().

    Args:
        files: The file dict passed to ReleaseInfoFake.
        expected: The expected _release_info output.
    """
    fake = ReleaseInfoFake(files)
    monkeypatch.setattr(version.glob, 'glob', fake.glob_fake)
    monkeypatch.setattr(version, 'open', fake.open_fake, raising=False)
    with caplog.at_level(logging.ERROR, 'misc'):
        assert version._release_info() == expected
    if files is None:
        assert caplog.messages == ["Error while reading fake-file."]


@pytest.mark.parametrize('equal', [True, False])
def test_path_info(monkeypatch, equal):
    """Test _path_info().

    Args:
        equal: Whether system data / data and system config / config are equal.
    """
    patches = {
        'config': lambda auto=False: (
            'AUTO CONFIG PATH' if auto and not equal
            else 'CONFIG PATH'),
        'data': lambda system=False: (
            'SYSTEM DATA PATH' if system and not equal
            else 'DATA PATH'),
        'cache': lambda: 'CACHE PATH',
        'runtime': lambda: 'RUNTIME PATH',
    }

    for name, val in patches.items():
        monkeypatch.setattr(version.standarddir, name, val)

    pathinfo = version._path_info()

    assert pathinfo['config'] == 'CONFIG PATH'
    assert pathinfo['data'] == 'DATA PATH'
    assert pathinfo['cache'] == 'CACHE PATH'
    assert pathinfo['runtime'] == 'RUNTIME PATH'

    if equal:
        assert 'auto config' not in pathinfo
        assert 'system data' not in pathinfo
    else:
        assert pathinfo['auto config'] == 'AUTO CONFIG PATH'
        assert pathinfo['system data'] == 'SYSTEM DATA PATH'


@pytest.fixture
def import_fake(stubs, monkeypatch):
    """Fixture to patch imports using ImportFake."""
    fake = stubs.ImportFake({mod: True for mod in version.MODULE_INFO}, monkeypatch)
    fake.patch()
    return fake


class TestModuleVersions:

    """Tests for _module_versions() and ModuleInfo."""

    def test_all_present(self, import_fake):
        """Test with all modules present in version 1.2.3."""
        expected = []
        for name in import_fake.modules:
            version.MODULE_INFO[name]._reset_cache()
            if '__version__' not in version.MODULE_INFO[name]._version_attributes:
                expected.append('{}: yes'.format(name))
            else:
                expected.append('{}: 1.2.3'.format(name))
        assert version._module_versions() == expected

    @pytest.mark.parametrize('module, idx, expected', [
        ('colorama', 1, 'colorama: no'),
        ('adblock', 5, 'adblock: no'),
    ])
    def test_missing_module(self, module, idx, expected, import_fake):
        """Test with a module missing.

        Args:
            module: The name of the missing module.
            idx: The index where the given text is expected.
            expected: The expected text.
        """
        import_fake.modules[module] = False
        # Needed after mocking the module
        mod_info = version.MODULE_INFO[module]
        mod_info._reset_cache()

        assert version._module_versions()[idx] == expected

        for method_name, expected_result in [
            ("is_installed", False),
            ("is_usable", False),
            ("get_version", None),
            ("is_outdated", None)
        ]:
            method = getattr(mod_info, method_name)
            # With hot cache
            mod_info._initialize_info()
            assert method() == expected_result
            # With cold cache
            mod_info._reset_cache()
            assert method() == expected_result

    def test_outdated_adblock(self, import_fake):
        """Test that warning is shown when adblock module is outdated."""
        mod_info = version.MODULE_INFO["adblock"]
        fake_version = "0.1.0"

        # Needed after mocking version attribute
        mod_info._reset_cache()

        assert mod_info.min_version is not None
        assert fake_version < mod_info.min_version
        import_fake.version = fake_version

        assert mod_info.is_installed()
        assert mod_info.is_outdated()
        assert not mod_info.is_usable()

        expected = f"adblock: {fake_version} (< {mod_info.min_version}, outdated)"
        assert version._module_versions()[5] == expected

    @pytest.mark.parametrize('attribute, expected_modules', [
        ('VERSION', ['colorama']),
        ('SIP_VERSION_STR', ['sip']),
        (None, []),
    ])
    def test_version_attribute(self, attribute, expected_modules, import_fake):
        """Test with a different version attribute.

        VERSION is tested for old colorama versions, and None to make sure
        things still work if some package suddenly doesn't have __version__.

        Args:
            attribute: The name of the version attribute.
            expected: The expected return value.
        """
        import_fake.version_attribute = attribute

        for mod_info in version.MODULE_INFO.values():
            # Invalidate the "version cache" since we just mocked some of the
            # attributes.
            mod_info._reset_cache()

        expected = []
        for name in import_fake.modules:
            mod_info = version.MODULE_INFO[name]
            if name in expected_modules:
                assert mod_info.get_version() == "1.2.3"
                expected.append('{}: 1.2.3'.format(name))
            else:
                assert mod_info.get_version() is None
                expected.append('{}: yes'.format(name))

        assert version._module_versions() == expected

    @pytest.mark.parametrize('name, has_version', [
        ('sip', False),
        ('colorama', True),
        ('jinja2', True),
        ('pygments', True),
        ('yaml', True),
        ('adblock', True),
        ('dataclasses', False),
        ('importlib_resources', False),
    ])
    def test_existing_attributes(self, name, has_version):
        """Check if all dependencies have an expected __version__ attribute.

        The aim of this test is to fail if modules suddenly don't have a
        __version__ attribute anymore in a newer version.

        Args:
            name: The name of the module to check.
            has_version: Whether a __version__ attribute is expected.
        """
        module = pytest.importorskip(name)
        assert hasattr(module, '__version__') == has_version

    def test_existing_sip_attribute(self):
        """Test if sip has a SIP_VERSION_STR attribute.

        The aim of this test is to fail if that gets missing in some future
        version of sip.
        """
        from qutebrowser.qt import sip
        assert isinstance(sip.SIP_VERSION_STR, str)


class TestOsInfo:

    """Tests for _os_info."""

    @pytest.mark.fake_os('linux')
    def test_linux_fake(self, monkeypatch):
        """Test with a fake Linux.

        No args because osver is set to '' if the OS is linux.
        """
        monkeypatch.setattr(version, '_release_info',
                            lambda: [('releaseinfo', 'Hello World')])
        ret = version._os_info()
        expected = ['OS Version: ', '',
                    '--- releaseinfo ---', 'Hello World']
        assert ret == expected

    @pytest.mark.fake_os('windows')
    def test_windows_fake(self, monkeypatch):
        """Test with a fake Windows."""
        monkeypatch.setattr(version.platform, 'win32_ver',
                            lambda: ('eggs', 'bacon', 'ham', 'spam'))
        ret = version._os_info()
        expected = ['OS Version: eggs, bacon, ham, spam']
        assert ret == expected

    @pytest.mark.fake_os('mac')
    @pytest.mark.parametrize('mac_ver, mac_ver_str', [
        (('x', ('', '', ''), 'y'), 'x, y'),
        (('', ('', '', ''), ''), ''),
        (('x', ('1', '2', '3'), 'y'), 'x, 1.2.3, y'),
    ])
    def test_mac_fake(self, monkeypatch, mac_ver, mac_ver_str):
        """Test with a fake macOS.

        Args:
            mac_ver: The tuple to set platform.mac_ver() to.
            mac_ver_str: The expected Mac version string in version._os_info().
        """
        monkeypatch.setattr(version.platform, 'mac_ver', lambda: mac_ver)
        ret = version._os_info()
        expected = ['OS Version: {}'.format(mac_ver_str)]
        assert ret == expected

    @pytest.mark.fake_os('posix')
    def test_posix_fake(self, monkeypatch):
        """Test with a fake posix platform."""
        uname_tuple = ('PosixOS', 'localhost', '1.0', '1.0', 'i386', 'i386')
        monkeypatch.setattr(version.platform, 'uname', lambda: uname_tuple)
        ret = version._os_info()
        expected = ['OS Version: PosixOS localhost 1.0 1.0 i386 i386']
        assert ret == expected

    @pytest.mark.fake_os('unknown')
    def test_unknown_fake(self):
        """Test with a fake unknown platform."""
        ret = version._os_info()
        expected = ['OS Version: ?']
        assert ret == expected

    @pytest.mark.linux
    def test_linux_real(self):
        """Make sure there are no exceptions with a real Linux."""
        version._os_info()

    @pytest.mark.windows
    def test_windows_real(self):
        """Make sure there are no exceptions with a real Windows."""
        version._os_info()

    @pytest.mark.mac
    def test_mac_real(self):
        """Make sure there are no exceptions with a real macOS."""
        version._os_info()

    @pytest.mark.posix
    def test_posix_real(self):
        """Make sure there are no exceptions with a real posix."""
        version._os_info()


class TestPDFJSVersion:

    """Tests for _pdfjs_version."""

    def test_not_found(self, mocker):
        mocker.patch('qutebrowser.utils.version.pdfjs.get_pdfjs_res_and_path',
                     side_effect=pdfjs.PDFJSNotFound('/build/pdf.js'))
        assert version._pdfjs_version() == 'no'

    def test_unknown(self, monkeypatch):
        monkeypatch.setattr(
            'qutebrowser.utils.version.pdfjs.get_pdfjs_res_and_path',
            lambda path: (b'foobar', None))
        assert version._pdfjs_version() == 'unknown (bundled)'

    @pytest.mark.parametrize('varname', [
        'PDFJS.version',  # v1.10.100 and older
        'var pdfjsVersion',  # v2.0.943
        'const pdfjsVersion',  # v2.5.207
    ])
    def test_known(self, monkeypatch, varname):
        pdfjs_code = textwrap.dedent("""
            // Initializing PDFJS global object (if still undefined)
            if (typeof PDFJS === 'undefined') {
              (typeof window !== 'undefined' ? window : this).PDFJS = {};
            }

            VARNAME = '1.2.109';
            PDFJS.build = '875588d';

            (function pdfjsWrapper() {
              // Use strict in our context only - users might not want it
              'use strict';
        """.replace('VARNAME', varname)).strip().encode('utf-8')
        monkeypatch.setattr(
            'qutebrowser.utils.version.pdfjs.get_pdfjs_res_and_path',
            lambda path: (pdfjs_code, '/foo/bar/pdf.js'))
        assert version._pdfjs_version() == '1.2.109 (/foo/bar/pdf.js)'

    def test_real_file(self, data_tmpdir):
        """Test against the real file if pdfjs was found."""
        try:
            pdfjs.get_pdfjs_res_and_path('build/pdf.js')
        except pdfjs.PDFJSNotFound:
            pytest.skip("No pdfjs found")
        ver = version._pdfjs_version()
        assert ver.split()[0] not in ['no', 'unknown'], ver


class TestWebEngineVersions:

    @pytest.mark.parametrize('version, expected', [
        (
            version.WebEngineVersions(
                webengine=utils.VersionNumber(5, 15, 2),
                chromium=None,
                source='UA'),
            "QtWebEngine 5.15.2",
        ),
        (
            version.WebEngineVersions(
                webengine=utils.VersionNumber(5, 15, 2),
                chromium='87.0.4280.144',
                source='UA'),
            "QtWebEngine 5.15.2, Chromium 87.0.4280.144",
        ),
        (
            version.WebEngineVersions(
                webengine=utils.VersionNumber(5, 15, 2),
                chromium='87.0.4280.144',
                source='faked'),
            "QtWebEngine 5.15.2, Chromium 87.0.4280.144 (from faked)",
        ),
    ])
    def test_str(self, version, expected):
        assert str(version) == expected

    @pytest.mark.parametrize('version, expected', [
        (
            version.WebEngineVersions(
                webengine=utils.VersionNumber(5, 15, 2),
                chromium=None,
                source='test'),
            None,
        ),
        (
            version.WebEngineVersions(
                webengine=utils.VersionNumber(5, 15, 2),
                chromium='87.0.4280.144',
                source='test'),
            87,
        ),
    ])
    def test_chromium_major(self, version, expected):
        assert version.chromium_major == expected

    def test_from_ua(self):
        ua = websettings.UserAgent(
            os_info='X11; Linux x86_64',
            webkit_version='537.36',
            upstream_browser_key='Chrome',
            upstream_browser_version='83.0.4103.122',
            qt_key='QtWebEngine',
            qt_version='5.15.2',
        )
        expected = version.WebEngineVersions(
            webengine=utils.VersionNumber(5, 15, 2),
            chromium='83.0.4103.122',
            source='UA',
        )
        assert version.WebEngineVersions.from_ua(ua) == expected

    def test_from_elf(self):
        elf_version = elf.Versions(webengine='5.15.2', chromium='83.0.4103.122')
        expected = version.WebEngineVersions(
            webengine=utils.VersionNumber(5, 15, 2),
            chromium='83.0.4103.122',
            source='ELF',
        )
        assert version.WebEngineVersions.from_elf(elf_version) == expected

    @pytest.mark.parametrize('pyqt_version, chromium_version', [
        ('5.12.10', '69.0.3497.128'),
        ('5.14.2', '77.0.3865.129'),
        ('5.15.1', '80.0.3987.163'),
        ('5.15.2', '83.0.4103.122'),
        ('5.15.3', '87.0.4280.144'),
        ('5.15.4', '87.0.4280.144'),
        ('5.15.5', '87.0.4280.144'),
    ])
    def test_from_pyqt(self, freezer, pyqt_version, chromium_version):
        if freezer and pyqt_version in ['5.15.3', '5.15.4', '5.15.5']:
            chromium_version = '83.0.4103.122'
            expected_pyqt_version = '5.15.2'
        else:
            expected_pyqt_version = pyqt_version

        expected = version.WebEngineVersions(
            webengine=utils.VersionNumber.parse(expected_pyqt_version),
            chromium=chromium_version,
            source='PyQt',
        )
        assert version.WebEngineVersions.from_pyqt(pyqt_version) == expected

    def test_real_chromium_version(self, qapp):
        """Compare the inferred Chromium version with the real one."""
        pyqt_webengine_version = version._get_pyqt_webengine_qt_version()
        if pyqt_webengine_version is None:
            if '.dev' in PYQT_VERSION_STR:
                pytest.skip("dev version of PyQt5")

            try:
                from PyQt5.QtWebEngine import (
                    PYQT_WEBENGINE_VERSION_STR, PYQT_WEBENGINE_VERSION)
            except ImportError as e:
                # QtWebKit or QtWebEngine < 5.13
                pytest.skip(str(e))

            if PYQT_WEBENGINE_VERSION >= 0x050F02:
                # Starting with Qt 5.15.2, we can only do bad guessing anyways...
                pytest.skip("Could be QtWebEngine 5.15.2 or 5.15.3")

            pyqt_webengine_version = PYQT_WEBENGINE_VERSION_STR

        versions = version.WebEngineVersions.from_pyqt(pyqt_webengine_version)
        inferred = versions.chromium

        webenginesettings.init_user_agent()
        real = webenginesettings.parsed_user_agent.upstream_browser_version

        assert inferred == real


class FakeQSslSocket:

    """Fake for the QSslSocket Qt class.

    Attributes:
        _version: What QSslSocket::sslLibraryVersionString() should return.
        _support: Whether SSL is supported.
    """

    def __init__(self, version=None, support=True):
        self._version = version
        self._support = support

    def supportsSsl(self):
        """Fake for QSslSocket::supportsSsl()."""
        return self._support

    def sslLibraryVersionString(self):
        """Fake for QSslSocket::sslLibraryVersionString()."""
        if self._version is None:
            raise utils.Unreachable("Got called with version None!")
        return self._version


_QTWE_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "QtWebEngine/5.14.0 Chrome/{} Safari/537.36")


class TestChromiumVersion:

    @pytest.fixture(autouse=True)
    def clear_parsed_ua(self, monkeypatch):
        pytest.importorskip('PyQt5.QtWebEngineWidgets')
        if webenginesettings is not None:
            # Not available with QtWebKit
            monkeypatch.setattr(webenginesettings, 'parsed_user_agent', None)

    def test_fake_ua(self, monkeypatch, caplog):
        ver = '77.0.3865.98'
        webenginesettings._init_user_agent_str(_QTWE_USER_AGENT.format(ver))

        assert version.qtwebengine_versions().chromium == ver

    def test_prefers_saved_user_agent(self, monkeypatch):
        webenginesettings._init_user_agent_str(_QTWE_USER_AGENT.format('87'))

        class FakeProfile:
            def defaultProfile(self):
                raise AssertionError("Should not be called")

        monkeypatch.setattr(webenginesettings, 'QWebEngineProfile', FakeProfile())

        version.qtwebengine_versions()

    def test_unpatched(self, qapp, cache_tmpdir, data_tmpdir, config_stub):
        assert version.qtwebengine_versions().chromium is not None

    def test_avoided(self, monkeypatch):
        versions = version.qtwebengine_versions(avoid_init=True)
        assert versions.source in ['ELF', 'importlib', 'PyQt', 'Qt']

    @pytest.fixture
    def patch_elf_fail(self, monkeypatch):
        """Simulate parsing the version from ELF to fail."""
        monkeypatch.setattr(elf, 'parse_webenginecore', lambda: None)

    @pytest.fixture
    def patch_old_pyqt(self, monkeypatch):
        """Simulate an old PyQt without PYQT_WEBENGINE_VERSION_STR."""
        monkeypatch.setattr(version, 'PYQT_WEBENGINE_VERSION_STR', None)

    @pytest.fixture
    def patch_no_importlib(self, monkeypatch, stubs):
        """Simulate missing importlib modules."""
        import_fake = stubs.ImportFake({
            'importlib_metadata': False,
            'importlib.metadata': False,
        }, monkeypatch)
        import_fake.patch()

    @pytest.fixture
    def importlib_patcher(self, monkeypatch):
        """Patch the importlib module."""
        def _patch(*, qt, qt5):
            try:
                import importlib.metadata as importlib_metadata
            except ImportError:
                importlib_metadata = pytest.importorskip("importlib_metadata")

            def _fake_version(name):
                if name == 'PyQtWebEngine-Qt':
                    outcome = qt
                elif name == 'PyQtWebEngine-Qt5':
                    outcome = qt5
                else:
                    raise utils.Unreachable(outcome)

                if outcome is None:
                    raise importlib_metadata.PackageNotFoundError(name)
                return outcome

            monkeypatch.setattr(importlib_metadata, 'version', _fake_version)

        return _patch

    @pytest.fixture
    def patch_importlib_no_package(self, importlib_patcher):
        """Simulate importlib not finding PyQtWebEngine-Qt[5]."""
        importlib_patcher(qt=None, qt5=None)

    @pytest.mark.parametrize('patches, sources', [
        (['elf_fail'], ['importlib', 'PyQt', 'Qt']),
        (['elf_fail', 'old_pyqt'], ['importlib', 'Qt']),
        (['elf_fail', 'no_importlib'], ['PyQt', 'Qt']),
        (['elf_fail', 'no_importlib', 'old_pyqt'], ['Qt']),
        (['elf_fail', 'importlib_no_package'], ['PyQt', 'Qt']),
        (['elf_fail', 'importlib_no_package', 'old_pyqt'], ['Qt']),
    ], ids=','.join)
    def test_simulated(self, request, patches, sources):
        """Test various simulated error conditions.

        This dynamically gets a list of fixtures (above) to do the patching. It then
        checks whether the version it got is from one of the expected sources. Depending
        on the environment this test is run in, some sources might fail "naturally",
        i.e. without any patching related to them.
        """
        for patch in patches:
            request.getfixturevalue(f'patch_{patch}')

        versions = version.qtwebengine_versions(avoid_init=True)
        assert versions.source in sources

    @pytest.mark.parametrize('qt, qt5, expected', [
        (None, '5.15.4', utils.VersionNumber(5, 15, 4)),
        ('5.15.3', None, utils.VersionNumber(5, 15, 3)),
        ('5.15.3', '5.15.4', utils.VersionNumber(5, 15, 4)),  # -Qt5 takes precedence
    ])
    def test_importlib(self, qt, qt5, expected, patch_elf_fail, importlib_patcher):
        """Test the importlib version logic with different Qt packages.

        With PyQtWebEngine 5.15.4, PyQtWebEngine-Qt was renamed to PyQtWebEngine-Qt5.
        """
        importlib_patcher(qt=qt, qt5=qt5)
        versions = version.qtwebengine_versions(avoid_init=True)
        assert versions.source == 'importlib'
        assert versions.webengine == expected


@dataclasses.dataclass
class VersionParams:

    name: str
    git_commit: bool = True
    frozen: bool = False
    qapp: bool = True
    with_webkit: bool = True
    known_distribution: bool = True
    ssl_support: bool = True
    autoconfig_loaded: bool = True
    config_py_loaded: bool = True


@pytest.mark.parametrize('params', [
    VersionParams('normal'),
    VersionParams('no-git-commit', git_commit=False),
    VersionParams('frozen', frozen=True),
    VersionParams('no-qapp', qapp=False),
    VersionParams('no-webkit', with_webkit=False),
    VersionParams('unknown-dist', known_distribution=False),
    VersionParams('no-ssl', ssl_support=False),
    VersionParams('no-autoconfig-loaded', autoconfig_loaded=False),
    VersionParams('no-config-py-loaded', config_py_loaded=False),
], ids=lambda param: param.name)
def test_version_info(params, stubs, monkeypatch, config_stub):
    """Test version.version_info()."""
    config.instance.config_py_loaded = params.config_py_loaded
    import_path = pathlib.Path('/IMPORTPATH').resolve()

    patches = {
        'qutebrowser.__file__': str(import_path / '__init__.py'),
        'qutebrowser.__version__': 'VERSION',
        '_git_str': lambda: ('GIT COMMIT' if params.git_commit else None),
        'platform.python_implementation': lambda: 'PYTHON IMPLEMENTATION',
        'platform.python_version': lambda: 'PYTHON VERSION',
        'sys.executable': 'EXECUTABLE PATH',
        'PYQT_VERSION_STR': 'PYQT VERSION',
        'earlyinit.qt_version': lambda: 'QT VERSION',
        '_module_versions': lambda: ['MODULE VERSION 1', 'MODULE VERSION 2'],
        '_pdfjs_version': lambda: 'PDFJS VERSION',
        'QSslSocket': FakeQSslSocket('SSL VERSION', params.ssl_support),
        'platform.platform': lambda: 'PLATFORM',
        'platform.architecture': lambda: ('ARCHITECTURE', ''),
        '_os_info': lambda: ['OS INFO 1', 'OS INFO 2'],
        '_path_info': lambda: {'PATH DESC': 'PATH NAME'},
        'objects.qapp': (stubs.FakeQApplication(style='STYLE', platform_name='PLATFORM')
                         if params.qapp else None),
        'QLibraryInfo.location': (lambda _loc: 'QT PATH'),
        'sql.version': lambda: 'SQLITE VERSION',
        '_uptime': lambda: datetime.timedelta(hours=1, minutes=23, seconds=45),
        'config.instance.yaml_loaded': params.autoconfig_loaded,
    }

    version.opengl_info.cache_clear()
    monkeypatch.setenv('QUTE_FAKE_OPENGL', 'VENDOR, 1.0 VERSION')

    substitutions = {
        'git_commit': '\nGit commit: GIT COMMIT' if params.git_commit else '',
        'style': '\nStyle: STYLE' if params.qapp else '',
        'platform_plugin': ('\nPlatform plugin: PLATFORM' if params.qapp
                            else ''),
        'opengl': '\nOpenGL: VENDOR, 1.0 VERSION' if params.qapp else '',
        'qt': 'QT VERSION',
        'frozen': str(params.frozen),
        'import_path': import_path,
        'python_path': 'EXECUTABLE PATH',
        'uptime': "1:23:45",
        'autoconfig_loaded': "yes" if params.autoconfig_loaded else "no",
    }

    patches['qtwebengine_versions'] = (
        lambda avoid_init: version.WebEngineVersions(
            webengine=utils.VersionNumber(1, 2, 3),
            chromium=None,
            source='faked',
        )
    )

    if params.config_py_loaded:
        substitutions["config_py_loaded"] = "{} has been loaded".format(
            standarddir.config_py())
    else:
        substitutions["config_py_loaded"] = "no config.py was loaded"

    if params.with_webkit:
        patches['qWebKitVersion'] = lambda: 'WEBKIT VERSION'
        patches['objects.backend'] = usertypes.Backend.QtWebKit
        substitutions['backend'] = 'new QtWebKit (WebKit WEBKIT VERSION)'
    else:
        monkeypatch.delattr(version, 'qtutils.qWebKitVersion', raising=False)
        patches['objects.backend'] = usertypes.Backend.QtWebEngine
        substitutions['backend'] = 'QtWebEngine 1.2.3 (from faked)'

    if params.known_distribution:
        patches['distribution'] = lambda: version.DistributionInfo(
            parsed=version.Distribution.arch, pretty='LINUX DISTRIBUTION', id='arch')
        substitutions['linuxdist'] = ('\nLinux distribution: '
                                      'LINUX DISTRIBUTION (arch)')
        substitutions['osinfo'] = ''
    else:
        patches['distribution'] = lambda: None
        substitutions['linuxdist'] = ''
        substitutions['osinfo'] = 'OS INFO 1\nOS INFO 2\n'

    substitutions['ssl'] = 'SSL VERSION' if params.ssl_support else 'no'

    for name, val in patches.items():
        monkeypatch.setattr(f'qutebrowser.utils.version.{name}', val)

    if params.frozen:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
    else:
        monkeypatch.delattr(sys, 'frozen', raising=False)

    template = version._LOGO.lstrip('\n') + textwrap.dedent("""
        qutebrowser vVERSION{git_commit}
        Backend: {backend}
        Qt: {qt}

        PYTHON IMPLEMENTATION: PYTHON VERSION
        PyQt: PYQT VERSION

        MODULE VERSION 1
        MODULE VERSION 2
        pdf.js: PDFJS VERSION
        sqlite: SQLITE VERSION
        QtNetwork SSL: {ssl}
        {style}{platform_plugin}{opengl}
        Platform: PLATFORM, ARCHITECTURE{linuxdist}
        Frozen: {frozen}
        Imported from {import_path}
        Using Python from {python_path}
        Qt library executable path: QT PATH, data path: QT PATH
        {osinfo}
        Paths:
        PATH DESC: PATH NAME

        Autoconfig loaded: {autoconfig_loaded}
        Config.py: {config_py_loaded}
        Uptime: {uptime}
    """.lstrip('\n'))

    expected = template.rstrip('\n').format(**substitutions)
    assert version.version_info() == expected


class TestOpenGLInfo:

    @pytest.fixture(autouse=True)
    def cache_clear(self):
        """Clear the lru_cache between tests."""
        version.opengl_info.cache_clear()

    def test_func(self, qapp):
        """Simply call version.opengl_info() and see if it doesn't crash."""
        pytest.importorskip("PyQt5.QtOpenGL")
        version.opengl_info()

    def test_func_fake(self, qapp, monkeypatch):
        monkeypatch.setenv('QUTE_FAKE_OPENGL', 'Outtel Inc., 3.0 Messiah 20.0')
        info = version.opengl_info()
        assert info.vendor == 'Outtel Inc.'
        assert info.version_str == '3.0 Messiah 20.0'
        assert info.version == (3, 0)
        assert info.vendor_specific == 'Messiah 20.0'

    @pytest.mark.parametrize('version_str, reason', [
        ('blah', 'missing space'),
        ('2,x blah', 'parsing int'),
    ])
    def test_parse_invalid(self, caplog, version_str, reason):
        with caplog.at_level(logging.WARNING):
            info = version.OpenGLInfo.parse(vendor="vendor",
                                            version=version_str)

        assert info.version is None
        assert info.vendor_specific is None
        assert info.vendor == 'vendor'
        assert info.version_str == version_str

        msg = "Failed to parse OpenGL version ({}): {}".format(
            reason, version_str)
        assert caplog.messages == [msg]

    @hypothesis.given(vendor=hypothesis.strategies.text(),
                      version_str=hypothesis.strategies.text())
    def test_parse_hypothesis(self, caplog, vendor, version_str):
        with caplog.at_level(logging.WARNING):
            info = version.OpenGLInfo.parse(vendor=vendor, version=version_str)

        assert info.vendor == vendor
        assert info.version_str == version_str
        assert vendor in str(info)
        assert version_str in str(info)

    @pytest.mark.parametrize('version_str, expected', [
        ("2.1 INTEL-10.36.26", (2, 1)),
        ("4.6 (Compatibility Profile) Mesa 20.0.7", (4, 6)),
        ("3.0 Mesa 20.0.7", (3, 0)),
        ("3.0 Mesa 20.0.6", (3, 0)),
        # Not from the wild, but can happen according to standards
        ("3.0.2 Mesa 20.0.6", (3, 0, 2)),
    ])
    def test_version(self, version_str, expected):
        info = version.OpenGLInfo.parse(vendor='vendor', version=version_str)
        assert info.version == expected

    def test_str_gles(self):
        info = version.OpenGLInfo(gles=True)
        assert str(info) == 'OpenGL ES'


@pytest.fixture
def pbclient(stubs):
    http_stub = stubs.HTTPPostStub()
    client = pastebin.PastebinClient(http_stub)
    yield client
    version.pastebin_url = None


def test_pastebin_version(pbclient, message_mock, monkeypatch, qtbot):
    """Test version.pastebin_version() sets the url."""
    monkeypatch.setattr(version, 'version_info', lambda: 'dummy')
    monkeypatch.setattr(utils, 'log_clipboard', True)

    version.pastebin_version(pbclient)
    pbclient.success.emit("https://www.example.com/\n")

    msg = message_mock.getmsg(usertypes.MessageLevel.info)
    expected_text = "Version url https://www.example.com/ yanked to clipboard."
    assert msg.text == expected_text
    assert version.pastebin_url == "https://www.example.com/"


def test_pastebin_version_twice(pbclient, monkeypatch):
    """Test whether calling pastebin_version twice sends no data."""
    monkeypatch.setattr(version, 'version_info', lambda: 'dummy')

    version.pastebin_version(pbclient)
    pbclient.success.emit("https://www.example.com/\n")

    pbclient.url = None
    pbclient.data = None
    version.pastebin_url = "https://www.example.org/"

    version.pastebin_version(pbclient)
    assert pbclient.url is None
    assert pbclient.data is None
    assert version.pastebin_url == "https://www.example.org/"


def test_pastebin_version_error(pbclient, caplog, message_mock, monkeypatch):
    """Test version.pastebin_version() with errors."""
    monkeypatch.setattr(version, 'version_info', lambda: 'dummy')

    version.pastebin_url = None
    with caplog.at_level(logging.ERROR):
        version.pastebin_version(pbclient)
        pbclient._client.error.emit("test")

    assert version.pastebin_url is None

    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    assert msg.text == "Failed to pastebin version info: test"


def test_uptime(monkeypatch, qapp):
    """Test _uptime runs and check if microseconds are dropped."""
    monkeypatch.setattr(objects, 'qapp', qapp)

    launch_time = datetime.datetime(1, 1, 1, 1, 1, 1, 1)
    monkeypatch.setattr(qapp, "launch_time", launch_time, raising=False)

    class FakeDateTime(datetime.datetime):
        now = lambda x=datetime.datetime(1, 1, 1, 1, 1, 1, 2): x
    monkeypatch.setattr(datetime, 'datetime', FakeDateTime)

    uptime_delta = version._uptime()
    assert uptime_delta == datetime.timedelta(0)
