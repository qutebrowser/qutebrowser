# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.utils.resources."""

import os.path
import zipfile
import pytest
from qutebrowser.utils import utils, resources


@pytest.mark.usefixtures('freezer')
class TestReadFile:

    @pytest.fixture
    def package_path(self, tmp_path):
        return tmp_path / 'qutebrowser'

    @pytest.fixture
    def html_path(self, package_path):
        path = package_path / 'html'
        path.mkdir(parents=True)

        for filename in ['test1.html', 'test2.html', 'README', 'unrelatedhtml']:
            (path / filename).touch()

        subdir = path / 'subdir'
        subdir.mkdir()
        (subdir / 'subdir-file.html').touch()

        return path

    @pytest.fixture
    def html_zip(self, tmp_path, html_path):
        if not hasattr(zipfile, 'Path'):
            pytest.skip("Needs zipfile.Path")

        zip_path = tmp_path / 'qutebrowser.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for path in html_path.rglob('*'):
                zf.write(path, path.relative_to(tmp_path))

            assert sorted(zf.namelist()) == [
                'qutebrowser/html/README',
                'qutebrowser/html/subdir/',
                'qutebrowser/html/subdir/subdir-file.html',
                'qutebrowser/html/test1.html',
                'qutebrowser/html/test2.html',
                'qutebrowser/html/unrelatedhtml',
            ]

        return zipfile.Path(zip_path) / 'qutebrowser'

    @pytest.fixture(params=['pathlib', 'zipfile'])
    def resource_root(self, request):
        """Resource files packaged either directly or via a zip."""
        if request.param == 'pathlib':
            request.getfixturevalue('html_path')
            return request.getfixturevalue('package_path')
        elif request.param == 'zipfile':
            return request.getfixturevalue('html_zip')
        raise utils.Unreachable(request.param)

    def test_glob_resources(self, resource_root):
        files = sorted(resources._glob(resource_root, 'html', '.html'))
        assert files == ['html/test1.html', 'html/test2.html']

    def test_glob_resources_subdir(self, resource_root):
        files = sorted(resources._glob(resource_root, 'html/subdir', '.html'))
        assert files == ['html/subdir/subdir-file.html']

    def test_readfile(self):
        """Read a test file."""
        content = resources.read_file(os.path.join('utils', 'testfile'))
        assert content.splitlines()[0] == "Hello World!"

    @pytest.mark.parametrize('filename', ['javascript/scroll.js',
                                          'html/error.html'])
    def test_read_cached_file(self, mocker, filename):
        resources.preload()
        m = mocker.patch('qutebrowser.utils.resources.importlib.resources.files')
        resources.read_file(filename)
        m.assert_not_called()

    def test_readfile_binary(self):
        """Read a test file in binary mode."""
        content = resources.read_file_binary(os.path.join('utils', 'testfile'))
        assert content.splitlines()[0] == b"Hello World!"

    @pytest.mark.parametrize('name', ['read_file', 'read_file_binary'])
    @pytest.mark.parametrize('fake_exception', [KeyError, FileNotFoundError, None])
    def test_not_found(self, name, fake_exception, monkeypatch):
        """Test behavior when a resources file wasn't found.

        With fake_exception, we emulate the rather odd error handling of certain Python
        versions: https://bugs.python.org/issue43063
        """
        class BrokenFileFake:

            def __init__(self, exc):
                self.exc = exc

            def read_bytes(self):
                raise self.exc("File does not exist")

            def read_text(self, encoding):
                raise self.exc("File does not exist")

            def __truediv__(self, _other):
                return self

        if fake_exception is not None:
            monkeypatch.setattr(resources.importlib.resources, 'files',
                                lambda _pkg: BrokenFileFake(fake_exception))

        meth = getattr(resources, name)
        with pytest.raises(FileNotFoundError):
            meth('doesnotexist')
