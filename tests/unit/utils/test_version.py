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

"""Tests for qutebrowser.utils.version."""

import io
import sys
import os.path
import subprocess
import contextlib
import builtins
import types
import importlib
import logging
import textwrap

import pytest

import qutebrowser
from qutebrowser.utils import version
from qutebrowser.browser import pdfjs


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

    @pytest.yield_fixture
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
        monkeypatch.setattr('qutebrowser.utils.version._git_str_subprocess',
                            fake.func)
        return fake

    def test_frozen_ok(self, commit_file_mock, monkeypatch):
        """Test with sys.frozen=True and a successful git-commit-id read."""
        monkeypatch.setattr(qutebrowser.utils.version.sys, 'frozen', True,
                            raising=False)
        commit_file_mock.return_value = 'deadbeef'
        assert version._git_str() == 'deadbeef'

    def test_frozen_oserror(self, caplog, commit_file_mock, monkeypatch):
        """Test with sys.frozen=True and OSError when reading git-commit-id."""
        monkeypatch.setattr(qutebrowser.utils.version.sys, 'frozen', True,
                            raising=False)
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
        monkeypatch.delattr('qutebrowser.utils.version.__file__')
        commit_file_mock.return_value = '0deadcode'
        with caplog.at_level(logging.ERROR, 'misc'):
            assert version._git_str() == '0deadcode'
        assert len(caplog.records) == 1
        assert caplog.records[0].message == "Error while getting git path"


def _has_git():
    """Check if git is installed."""
    try:
        subprocess.check_call(['git', '--version'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
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
            if os.name == 'nt':
                # If we don't call this with shell=True it might fail under
                # some environments on Windows...
                # http://bugs.python.org/issue24493
                subprocess.check_call(
                    'git -C "{}" {}'.format(tmpdir, ' '.join(args)),
                    env=env, shell=True)
            else:
                subprocess.check_call(
                    ['git', '-C', str(tmpdir)] + list(args), env=env)

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
        assert ret == 'foobar (1970-01-01 01:00:00 +0100)'

    def test_missing_dir(self, tmpdir):
        """Test with a directory which doesn't exist."""
        ret = version._git_str_subprocess(str(tmpdir / 'does-not-exist'))
        assert ret is None

    @pytest.mark.parametrize('exc', [
        OSError,
        subprocess.CalledProcessError(1, 'foobar')
    ])
    def test_exception(self, exc, mocker, tmpdir):
        """Test with subprocess.check_output raising an exception.

        Args:
            exc: The exception to raise.
        """
        m = mocker.patch('qutebrowser.utils.version.os')
        m.path.isdir.return_value = True
        mocker.patch('qutebrowser.utils.version.subprocess.check_output',
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
            return sorted(list(self._files))

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
    monkeypatch.setattr('qutebrowser.utils.version.glob.glob', fake.glob_fake)
    monkeypatch.setattr(version, 'open', fake.open_fake, raising=False)
    with caplog.at_level(logging.ERROR, 'misc'):
        assert version._release_info() == expected
    if files is None:
        assert len(caplog.records) == 1
        assert caplog.records[0].message == "Error while reading fake-file."


class ImportFake:

    """A fake for __import__ which is used by the import_fake fixture.

    Attributes:
        exists: A dict mapping module names to bools. If True, the import will
                success. Otherwise, it'll fail with ImportError.
        version_attribute: The name to use in the fake modules for the version
                           attribute.
        version: The version to use for the modules.
        _real_import: Saving the real __import__ builtin so the imports can be
                      done normally for modules not in self.exists.
    """

    def __init__(self):
        self.exists = {
            'sip': True,
            'colorama': True,
            'pypeg2': True,
            'jinja2': True,
            'pygments': True,
            'yaml': True,
            'cssutils': True,
            'typing': True,
            'PyQt5.QtWebEngineWidgets': True,
        }
        self.version_attribute = '__version__'
        self.version = '1.2.3'
        self._real_import = builtins.__import__

    def _do_import(self, name):
        """Helper for fake_import and fake_importlib_import to do the work.

        Return:
            The imported fake module, or None if normal importing should be
            used.
        """
        if name not in self.exists:
            # Not one of the modules to test -> use real import
            return None
        elif self.exists[name]:
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
            return importlib.import_module(name)


@pytest.fixture
def import_fake(monkeypatch):
    """Fixture to patch imports using ImportFake."""
    fake = ImportFake()
    monkeypatch.setattr('builtins.__import__', fake.fake_import)
    monkeypatch.setattr('qutebrowser.utils.version.importlib.import_module',
                        fake.fake_importlib_import)
    return fake


class TestModuleVersions:

    """Tests for _module_versions()."""

    @pytest.mark.usefixtures('import_fake')
    def test_all_present(self):
        """Test with all modules present in version 1.2.3."""
        expected = ['sip: yes', 'colorama: 1.2.3', 'pypeg2: 1.2.3',
                    'jinja2: 1.2.3', 'pygments: 1.2.3', 'yaml: 1.2.3',
                    'cssutils: 1.2.3', 'typing: yes',
                    'PyQt5.QtWebEngineWidgets: yes']
        assert version._module_versions() == expected

    @pytest.mark.parametrize('module, idx, expected', [
        ('colorama', 1, 'colorama: no'),
        ('cssutils', 6, 'cssutils: no'),
        ('typing', 7, 'typing: no'),
    ])
    def test_missing_module(self, module, idx, expected, import_fake):
        """Test with a module missing.

        Args:
            module: The name of the missing module.
            idx: The index where the given text is expected.
            expected: The expected text.
        """
        import_fake.exists[module] = False
        assert version._module_versions()[idx] == expected

    @pytest.mark.parametrize('value, expected', [
        ('VERSION', ['sip: yes', 'colorama: 1.2.3', 'pypeg2: yes',
                     'jinja2: yes', 'pygments: yes', 'yaml: yes',
                     'cssutils: yes', 'typing: yes',
                     'PyQt5.QtWebEngineWidgets: yes']),
        ('SIP_VERSION_STR', ['sip: 1.2.3', 'colorama: yes', 'pypeg2: yes',
                             'jinja2: yes', 'pygments: yes', 'yaml: yes',
                             'cssutils: yes', 'typing: yes',
                             'PyQt5.QtWebEngineWidgets: yes']),
        (None, ['sip: yes', 'colorama: yes', 'pypeg2: yes', 'jinja2: yes',
                'pygments: yes', 'yaml: yes', 'cssutils: yes', 'typing: yes',
                'PyQt5.QtWebEngineWidgets: yes']),
    ])
    def test_version_attribute(self, value, expected, import_fake):
        """Test with a different version attribute.

        VERSION is tested for old colorama versions, and None to make sure
        things still work if some package suddenly doesn't have __version__.

        Args:
            value: The name of the version attribute.
            expected: The expected return value.
        """
        import_fake.version_attribute = value
        assert version._module_versions() == expected

    @pytest.mark.parametrize('name, has_version', [
        ('sip', False),
        ('colorama', True),
        ('pypeg2', True),
        ('jinja2', True),
        ('pygments', True),
        ('yaml', True),
        ('cssutils', True),
    ])
    def test_existing_attributes(self, name, has_version):
        """Check if all dependencies have an expected __version__ attribute.

        The aim of this test is to fail if modules suddenly don't have a
        __version__ attribute anymore in a newer version.

        Args:
            name: The name of the module to check.
            has_version: Whether a __version__ attribute is expected.
        """
        module = importlib.import_module(name)
        assert hasattr(module, '__version__') == has_version

    def test_existing_sip_attribute(self):
        """Test if sip has a SIP_VERSION_STR attribute.

        The aim of this test is to fail if that gets missing in some future
        version of sip.
        """
        import sip
        assert isinstance(sip.SIP_VERSION_STR, str)


class TestOsInfo:

    """Tests for _os_info."""

    def test_linux_fake(self, monkeypatch):
        """Test with a fake Linux.

        No args because osver is set to '' if the OS is linux.
        """
        monkeypatch.setattr('qutebrowser.utils.version.sys.platform', 'linux')
        monkeypatch.setattr('qutebrowser.utils.version._release_info',
                            lambda: [('releaseinfo', 'Hello World')])
        ret = version._os_info()
        expected = ['OS Version: ', '',
                    '--- releaseinfo ---', 'Hello World']
        assert ret == expected

    def test_windows_fake(self, monkeypatch):
        """Test with a fake Windows."""
        monkeypatch.setattr('qutebrowser.utils.version.sys.platform', 'win32')
        monkeypatch.setattr('qutebrowser.utils.version.platform.win32_ver',
                            lambda: ('eggs', 'bacon', 'ham', 'spam'))
        ret = version._os_info()
        expected = ['OS Version: eggs, bacon, ham, spam']
        assert ret == expected

    @pytest.mark.parametrize('mac_ver, mac_ver_str', [
        (('x', ('', '', ''), 'y'), 'x, y'),
        (('', ('', '', ''), ''), ''),
        (('x', ('1', '2', '3'), 'y'), 'x, 1.2.3, y'),
    ])
    def test_os_x_fake(self, monkeypatch, mac_ver, mac_ver_str):
        """Test with a fake OS X.

        Args:
            mac_ver: The tuple to set platform.mac_ver() to.
            mac_ver_str: The expected Mac version string in version._os_info().
        """
        monkeypatch.setattr('qutebrowser.utils.version.sys.platform', 'darwin')
        monkeypatch.setattr('qutebrowser.utils.version.platform.mac_ver',
                            lambda: mac_ver)
        ret = version._os_info()
        expected = ['OS Version: {}'.format(mac_ver_str)]
        assert ret == expected

    def test_unknown_fake(self, monkeypatch):
        """Test with a fake unknown sys.platform."""
        monkeypatch.setattr('qutebrowser.utils.version.sys.platform',
                            'toaster')
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

    @pytest.mark.osx
    def test_os_x_real(self):
        """Make sure there are no exceptions with a real OS X."""
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

    def test_real_file(self):
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
    """

    def __init__(self, version=None):
        self._version = version

    def supportsSsl(self):
        """Fake for QSslSocket::supportsSsl()."""
        return True

    def sslLibraryVersionString(self):
        """Fake for QSslSocket::sslLibraryVersionString()."""
        if self._version is None:
            raise AssertionError("Got called with version None!")
        return self._version


@pytest.mark.parametrize('git_commit, harfbuzz, frozen, style, equal_qt', [
    (True, True, False, True, True),  # normal
    (False, True, False, True, True),  # no git commit
    (True, False, False, True, True),  # HARFBUZZ unset
    (True, True, True, True, True),  # frozen
    (True, True, True, False, True),  # no style
    (True, True, False, True, False),  # different Qt
])
def test_version_output(git_commit, harfbuzz, frozen, style, equal_qt,
                        stubs, monkeypatch):
    """Test version.version()."""
    import_path = os.path.abspath('/IMPORTPATH')
    patches = {
        'qutebrowser.__file__': os.path.join(import_path, '__init__.py'),
        'qutebrowser.__version__': 'VERSION',
        '_git_str': lambda: ('GIT COMMIT' if git_commit else None),
        'platform.python_implementation': lambda: 'PYTHON IMPLEMENTATION',
        'platform.python_version': lambda: 'PYTHON VERSION',
        'PYQT_VERSION_STR': 'PYQT VERSION',
        'QT_VERSION_STR': 'QT VERSION',
        'qVersion': (lambda:
                     'QT VERSION' if equal_qt else 'QT RUNTIME VERSION'),
        '_module_versions': lambda: ['MODULE VERSION 1', 'MODULE VERSION 2'],
        '_pdfjs_version': lambda: 'PDFJS VERSION',
        'qWebKitVersion': lambda: 'WEBKIT VERSION',
        'QSslSocket': FakeQSslSocket('SSL VERSION'),
        'platform.platform': lambda: 'PLATFORM',
        'platform.architecture': lambda: ('ARCHITECTURE', ''),
        '_os_info': lambda: ['OS INFO 1', 'OS INFO 2'],
        'QApplication': (stubs.FakeQApplication(style='STYLE') if style else
                         stubs.FakeQApplication(instance=None)),
    }

    for attr, val in patches.items():
        monkeypatch.setattr('qutebrowser.utils.version.' + attr, val)

    monkeypatch.setenv('DESKTOP_SESSION', 'DESKTOP')

    if harfbuzz:
        monkeypatch.setenv('QT_HARFBUZZ', 'HARFBUZZ')
    else:
        monkeypatch.delenv('QT_HARFBUZZ', raising=False)

    if frozen:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
    else:
        monkeypatch.delattr(sys, 'frozen', raising=False)

    template = textwrap.dedent("""
        qutebrowser vVERSION
        {git_commit}
        PYTHON IMPLEMENTATION: PYTHON VERSION
        Qt: {qt}
        PyQt: PYQT VERSION

        MODULE VERSION 1
        MODULE VERSION 2
        pdf.js: PDFJS VERSION
        Webkit: WEBKIT VERSION
        Harfbuzz: {harfbuzz}
        SSL: SSL VERSION
        {style}
        Platform: PLATFORM, ARCHITECTURE
        Desktop: DESKTOP
        Frozen: {frozen}
        Imported from {import_path}
        OS INFO 1
        OS INFO 2
    """.lstrip('\n'))

    substitutions = {
        'git_commit': 'Git commit: GIT COMMIT\n' if git_commit else '',
        'style': '\nStyle: STYLE' if style else '',
        'qt': ('QT VERSION' if equal_qt else
               'QT RUNTIME VERSION (compiled QT VERSION)'),
        'harfbuzz': 'HARFBUZZ' if harfbuzz else 'system',
        'frozen': str(frozen),
        'import_path': import_path,
    }

    expected = template.rstrip('\n').format(**substitutions)
    assert version.version() == expected
