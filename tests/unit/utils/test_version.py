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

"""Tests for qutebrowser.utils.version."""

import io
import sys
import collections
import os.path
import subprocess
import contextlib
import builtins  # noqa https://github.com/JBKahn/flake8-debugger/issues/20
import types
import importlib
import logging
import textwrap
import datetime

import attr
import pkg_resources
import pytest
import hypothesis
import hypothesis.strategies

import qutebrowser
from qutebrowser.config import config
from qutebrowser.utils import version, usertypes, utils, standarddir
from qutebrowser.misc import pastebin
from qutebrowser.browser import pdfjs


@pytest.mark.parametrize('os_release, expected', [
    # No file
    (None, None),
    # Invalid file
    ("\n# foo\n foo=bar=baz",
     version.DistributionInfo(id=None, parsed=version.Distribution.unknown,
                              version=None, pretty='Unknown')),
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
         id='arch', parsed=version.Distribution.arch, version=None,
         pretty='Arch Linux')),
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
         id='ubuntu', parsed=version.Distribution.ubuntu,
         version=pkg_resources.parse_version('14.4'),
         pretty='Ubuntu 14.04.5 LTS')),
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
         id='ubuntu', parsed=version.Distribution.ubuntu,
         version=pkg_resources.parse_version('17.4'),
         pretty='Ubuntu 17.04')),
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
         version=pkg_resources.parse_version('8'),
         pretty='Debian GNU/Linux 8 (jessie)')),
    # Void Linux
    ("""
        NAME="void"
        ID="void"
        DISTRIB_ID="void"
        PRETTY_NAME="void"
     """,
     version.DistributionInfo(
         id='void', parsed=version.Distribution.void,
         version=None, pretty='void')),
    # Gentoo
    ("""
        NAME=Gentoo
        ID=gentoo
        PRETTY_NAME="Gentoo/Linux"
     """,
     version.DistributionInfo(
         id='gentoo', parsed=version.Distribution.gentoo,
         version=None, pretty='Gentoo/Linux')),
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
         version=pkg_resources.parse_version('25'),
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
         version=pkg_resources.parse_version('42.2'),
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
         version=pkg_resources.parse_version('18.1'),
         pretty='Linux Mint 18.1')),
    # Manjaro
    ("""
        NAME="Manjaro Linux"
        ID=manjaro
        PRETTY_NAME="Manjaro Linux"
     """,
     version.DistributionInfo(
         id='manjaro', parsed=version.Distribution.manjaro,
         version=None, pretty='Manjaro Linux')),
    # Funtoo
    ("""
        ID="funtoo"
        NAME="Funtoo GNU/Linux"
        PRETTY_NAME="Linux"
     """,
     version.DistributionInfo(
         id='funtoo', parsed=version.Distribution.gentoo,
         version=None, pretty='Funtoo GNU/Linux')),
    # KDE Platform
    ("""
        NAME=KDE
        VERSION="5.12 (Flatpak runtime)"
        VERSION_ID="5.12"
        ID=org.kde.Platform
    """,
     version.DistributionInfo(
         id='org.kde.Platform', parsed=version.Distribution.kde_flatpak,
         version=pkg_resources.parse_version('5.12'),
         pretty='KDE')),
    # No PRETTY_NAME
    ("""
        NAME="Tux"
        ID=tux
     """,
     version.DistributionInfo(
         id='tux', parsed=version.Distribution.unknown,
         version=None, pretty='Tux')),
    # Invalid multi-line value
    ("""
        ID=tux
        PRETTY_NAME="Multiline
        Text"
     """,
     version.DistributionInfo(
         id='tux', parsed=version.Distribution.unknown,
         version=None, pretty='Multiline')),
])
def test_distribution(tmpdir, monkeypatch, os_release, expected):
    os_release_file = tmpdir / 'os-release'
    if os_release is not None:
        os_release_file.write(textwrap.dedent(os_release))
    monkeypatch.setenv('QUTE_FAKE_OS_RELEASE', str(os_release_file))

    assert version.distribution() == expected


@pytest.mark.parametrize('distribution, expected', [
    (None, False),
    (version.DistributionInfo(
        id='org.kde.Platform', parsed=version.Distribution.kde_flatpak,
        version=pkg_resources.parse_version('5.12'),
        pretty='Unknown'), True),
    (version.DistributionInfo(
        id='arch', parsed=version.Distribution.arch, version=None,
        pretty='Arch Linux'), False)
])
def test_is_sandboxed(monkeypatch, distribution, expected):
    monkeypatch.setattr(version, "distribution", lambda: distribution)
    assert version.is_sandboxed() == expected


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
        gitpath = os.path.normpath(gitpath)
        expected = os.path.abspath(os.path.join(
            os.path.dirname(qutebrowser.__file__), os.pardir))
        assert gitpath == expected
        return retval


class TestGitStr:

    """Tests for _git_str()."""

    @pytest.fixture
    def commit_file_mock(self, mocker):
        """Fixture providing a mock for utils.read_file for git-commit-id.

        On fixture teardown, it makes sure it got called with git-commit-id as
        argument.
        """
        mocker.patch('qutebrowser.utils.version.subprocess',
                     side_effect=AssertionError)
        m = mocker.patch('qutebrowser.utils.version.utils.read_file')
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
        mocker.patch('qutebrowser.utils.version.utils.read_file',
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
    def git_repo(self, tmpdir):
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
                # http://bugs.python.org/issue24493
                subprocess.run(
                    'git -C "{}" {}'.format(tmpdir, ' '.join(args)),
                    env=env, check=True, shell=True)
            else:
                subprocess.run(
                    ['git', '-C', str(tmpdir)] + list(args),
                    check=True, env=env)

        (tmpdir / 'file').write_text("Hello World!", encoding='utf-8')
        _git('init')
        _git('add', 'file')
        _git('commit', '-am', 'foo', '--no-verify', '--no-edit',
             '--no-post-rewrite', '--quiet', '--no-gpg-sign')
        _git('tag', 'foobar')
        return tmpdir

    @needs_git
    def test_real_git(self, git_repo):
        """Test with a real git repository."""
        ret = version._git_str_subprocess(str(git_repo))
        assert ret == '6e4b65a (1970-01-01 01:00:00 +0100)'

    def test_missing_dir(self, tmpdir):
        """Test with a directory which doesn't exist."""
        ret = version._git_str_subprocess(str(tmpdir / 'does-not-exist'))
        assert ret is None

    @pytest.mark.parametrize('exc', [
        OSError,
        subprocess.CalledProcessError(1, 'foobar')
    ])
    def test_exception(self, exc, mocker, tmpdir):
        """Test with subprocess.run raising an exception.

        Args:
            exc: The exception to raise.
        """
        m = mocker.patch('qutebrowser.utils.version.os')
        m.path.isdir.return_value = True
        mocker.patch('qutebrowser.utils.version.subprocess.run',
                     side_effect=exc)
        ret = version._git_str_subprocess(str(tmpdir))
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


class ImportFake:

    """A fake for __import__ which is used by the import_fake fixture.

    Attributes:
        modules: A dict mapping module names to bools. If True, the import will
                 success. Otherwise, it'll fail with ImportError.
        version_attribute: The name to use in the fake modules for the version
                           attribute.
        version: The version to use for the modules.
        _real_import: Saving the real __import__ builtin so the imports can be
                      done normally for modules not in self. modules.
    """

    def __init__(self):
        self.modules = collections.OrderedDict([
            ('sip', True),
            ('colorama', True),
            ('pypeg2', True),
            ('jinja2', True),
            ('pygments', True),
            ('yaml', True),
            ('cssutils', True),
            ('attr', True),
            ('PyQt5.QtWebEngineWidgets', True),
            ('PyQt5.QtWebEngine', True),
            ('PyQt5.QtWebKitWidgets', True),
        ])
        self.no_version_attribute = ['sip',
                                     'PyQt5.QtWebEngineWidgets',
                                     'PyQt5.QtWebKitWidgets',
                                     'PyQt5.QtWebEngine']
        self.version_attribute = '__version__'
        self.version = '1.2.3'
        self._real_import = builtins.__import__
        self._real_importlib_import = importlib.import_module

    def _do_import(self, name):
        """Helper for fake_import and fake_importlib_import to do the work.

        Return:
            The imported fake module, or None if normal importing should be
            used.
        """
        if name not in self.modules:
            # Not one of the modules to test -> use real import
            return None
        elif self.modules[name]:
            ns = types.SimpleNamespace()
            if self.version_attribute is not None:
                setattr(ns, self.version_attribute, self.version)
            return ns
        else:
            raise ImportError("Fake ImportError for {}.".format(name))

    def fake_import(self, name, *args, **kwargs):
        """Fake for the builtin __import__."""
        module = self._do_import(name)
        if module is not None:
            return module
        else:
            return self._real_import(name, *args, **kwargs)

    def fake_importlib_import(self, name):
        """Fake for importlib.import_module."""
        module = self._do_import(name)
        if module is not None:
            return module
        else:
            return self._real_importlib_import(name)


@pytest.fixture
def import_fake(monkeypatch):
    """Fixture to patch imports using ImportFake."""
    fake = ImportFake()
    monkeypatch.setattr('builtins.__import__', fake.fake_import)
    monkeypatch.setattr(version.importlib, 'import_module',
                        fake.fake_importlib_import)
    return fake


class TestModuleVersions:

    """Tests for _module_versions()."""

    def test_all_present(self, import_fake):
        """Test with all modules present in version 1.2.3."""
        expected = []
        for name in import_fake.modules:
            if name in import_fake.no_version_attribute:
                expected.append('{}: yes'.format(name))
            else:
                expected.append('{}: 1.2.3'.format(name))
        assert version._module_versions() == expected

    @pytest.mark.parametrize('module, idx, expected', [
        ('colorama', 1, 'colorama: no'),
        ('cssutils', 6, 'cssutils: no'),
    ])
    def test_missing_module(self, module, idx, expected, import_fake):
        """Test with a module missing.

        Args:
            module: The name of the missing module.
            idx: The index where the given text is expected.
            expected: The expected text.
        """
        import_fake.modules[module] = False
        assert version._module_versions()[idx] == expected

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
        expected = []
        for name in import_fake.modules:
            if name in expected_modules:
                expected.append('{}: 1.2.3'.format(name))
            else:
                expected.append('{}: yes'.format(name))
        assert version._module_versions() == expected

    @pytest.mark.parametrize('name, has_version', [
        ('sip', False),
        ('colorama', True),
        ('pypeg2', True),
        ('jinja2', True),
        ('pygments', True),
        ('yaml', True),
        ('cssutils', True),
        ('attr', True),
    ])
    def test_existing_attributes(self, name, has_version):
        """Check if all dependencies have an expected __version__ attribute.

        The aim of this test is to fail if modules suddenly don't have a
        __version__ attribute anymore in a newer version.

        Args:
            name: The name of the module to check.
            has_version: Whether a __version__ attribute is expected.
        """
        if name == 'cssutils':
            pytest.importorskip(name)
        module = importlib.import_module(name)
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
        'PDFJS.version',  # older versions
        'var pdfjsVersion',  # newer versions
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


def test_chromium_version(monkeypatch, caplog):
    pytest.importorskip('PyQt5.QtWebEngineWidgets')

    ver = '77.0.3865.98'
    version.webenginesettings._init_user_agent_str(
        _QTWE_USER_AGENT.format(ver))

    assert version._chromium_version() == ver


def test_chromium_version_no_webengine(monkeypatch):
    monkeypatch.setattr(version, 'webenginesettings', None)
    assert version._chromium_version() == 'unavailable'


def test_chromium_version_prefers_saved_user_agent(monkeypatch):
    pytest.importorskip('PyQt5.QtWebEngineWidgets')
    version.webenginesettings._init_user_agent_str(_QTWE_USER_AGENT)

    class FakeProfile:
        def defaultProfile(self):
            raise AssertionError("Should not be called")

    monkeypatch.setattr(version.webenginesettings, 'QWebEngineProfile',
                        FakeProfile())

    version._chromium_version()


def test_chromium_version_unpatched(qapp, cache_tmpdir, data_tmpdir,
                                    config_stub):
    pytest.importorskip('PyQt5.QtWebEngineWidgets')
    assert version._chromium_version() not in ['', 'unknown', 'unavailable']


@attr.s
class VersionParams:

    name = attr.ib()
    git_commit = attr.ib(True)
    frozen = attr.ib(False)
    qapp = attr.ib(True)
    with_webkit = attr.ib(True)
    known_distribution = attr.ib(True)
    ssl_support = attr.ib(True)
    autoconfig_loaded = attr.ib(True)
    config_py_loaded = attr.ib(True)


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
    import_path = os.path.abspath('/IMPORTPATH')

    patches = {
        'qutebrowser.__file__': os.path.join(import_path, '__init__.py'),
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
        'QApplication': (stubs.FakeQApplication(style='STYLE',
                                                platform_name='PLATFORM')
                         if params.qapp else
                         stubs.FakeQApplication(instance=None)),
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

    ua = _QTWE_USER_AGENT.format('CHROMIUMVERSION')
    if version.webenginesettings is None:
        patches['_chromium_version'] = lambda: 'CHROMIUMVERSION'
    else:
        version.webenginesettings._init_user_agent_str(ua)

    if params.config_py_loaded:
        substitutions["config_py_loaded"] = "{} has been loaded".format(
            standarddir.config_py())
    else:
        substitutions["config_py_loaded"] = "no config.py was loaded"

    if params.with_webkit:
        patches['qWebKitVersion'] = lambda: 'WEBKIT VERSION'
        patches['objects.backend'] = usertypes.Backend.QtWebKit
        patches['webenginesettings'] = None
        substitutions['backend'] = 'new QtWebKit (WebKit WEBKIT VERSION)'
    else:
        monkeypatch.delattr(version, 'qtutils.qWebKitVersion', raising=False)
        patches['objects.backend'] = usertypes.Backend.QtWebEngine
        substitutions['backend'] = 'QtWebEngine (Chromium CHROMIUMVERSION)'

    if params.known_distribution:
        patches['distribution'] = lambda: version.DistributionInfo(
            parsed=version.Distribution.arch, version=None,
            pretty='LINUX DISTRIBUTION', id='arch')
        substitutions['linuxdist'] = ('\nLinux distribution: '
                                      'LINUX DISTRIBUTION (arch)')
        substitutions['osinfo'] = ''
    else:
        patches['distribution'] = lambda: None
        substitutions['linuxdist'] = ''
        substitutions['osinfo'] = 'OS INFO 1\nOS INFO 2\n'

    substitutions['ssl'] = 'SSL VERSION' if params.ssl_support else 'no'

    for name, val in patches.items():
        monkeypatch.setattr('qutebrowser.utils.version.' + name, val)

    if params.frozen:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
    else:
        monkeypatch.delattr(sys, 'frozen', raising=False)

    template = textwrap.dedent("""
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

        if info.version is not None:
            reconstructed = ' '.join(['.'.join(str(part)
                                               for part in info.version),
                                      info.vendor_specific])
            assert reconstructed == info.version_str

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
    monkeypatch.setattr('qutebrowser.utils.version.version_info',
                        lambda: "dummy")
    monkeypatch.setattr('qutebrowser.utils.utils.log_clipboard', True)

    version.pastebin_version(pbclient)
    pbclient.success.emit("https://www.example.com/\n")

    msg = message_mock.getmsg(usertypes.MessageLevel.info)
    expected_text = "Version url https://www.example.com/ yanked to clipboard."
    assert msg.text == expected_text
    assert version.pastebin_url == "https://www.example.com/"


def test_pastebin_version_twice(pbclient, monkeypatch):
    """Test whether calling pastebin_version twice sends no data."""
    monkeypatch.setattr('qutebrowser.utils.version.version_info',
                        lambda: "dummy")

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
    monkeypatch.setattr('qutebrowser.utils.version.version_info',
                        lambda: "dummy")

    version.pastebin_url = None
    with caplog.at_level(logging.ERROR):
        version.pastebin_version(pbclient)
        pbclient._client.error.emit("test")

    assert version.pastebin_url is None

    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    assert msg.text == "Failed to pastebin version info: test"


def test_uptime(monkeypatch, qapp):
    """Test _uptime runs and check if microseconds are dropped."""
    launch_time = datetime.datetime(1, 1, 1, 1, 1, 1, 1)
    monkeypatch.setattr(qapp, "launch_time", launch_time, raising=False)

    class FakeDateTime(datetime.datetime):
        now = lambda x=datetime.datetime(1, 1, 1, 1, 1, 1, 2): x
    monkeypatch.setattr('datetime.datetime', FakeDateTime)

    uptime_delta = version._uptime()
    assert uptime_delta == datetime.timedelta(0)
