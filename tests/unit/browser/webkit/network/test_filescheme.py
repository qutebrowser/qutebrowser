# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015-2018 Antoni Boucher (antoyo) <bouanto@zoho.com>
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

import pathlib
import dataclasses
from typing import List

import pytest
import bs4
from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QNetworkRequest

from qutebrowser.browser.webkit.network import filescheme
from qutebrowser.utils import urlutils, utils
from helpers import testutils


@pytest.mark.parametrize('create_file, create_dir, filterfunc, expected', [
    (True, False, pathlib.Path.is_file, True),
    (True, False, pathlib.Path.is_dir, False),

    (False, True, pathlib.Path.is_file, False),
    (False, True, pathlib.Path.is_dir, True),

    (False, False, pathlib.Path.is_file, False),
    (False, False, pathlib.Path.is_dir, False),
])
def test_get_file_list(tmp_path, create_file, create_dir, filterfunc, expected):
    """Test get_file_list."""
    path = tmp_path / 'foo'
    if create_file:
        path.touch()
    if create_dir:
        path.mkdir()

    all_files = list(tmp_path.iterdir())

    result = filescheme.get_file_list(tmp_path, all_files, filterfunc)
    item = {'name': 'foo', 'absname': str(path)}
    assert (item in result) == expected


class TestIsRoot:

    @pytest.mark.windows
    @pytest.mark.parametrize('directory, is_root', [
        ('C:\\foo\\bar', False),
        ('C:\\foo\\', False),
        ('C:\\foo', False),
        ('C:\\', True)
    ])
    def test_windows(self, directory, is_root):
        assert filescheme.is_root(pathlib.Path(directory)) == is_root

    @pytest.mark.posix
    @pytest.mark.parametrize('directory, is_root', [
        ('/foo/bar', False),
        ('/foo/', False),
        ('/foo', False),
        ('/', True)
    ])
    def test_posix(self, directory, is_root):
        assert filescheme.is_root(pathlib.Path(directory)) == is_root


def _file_url(path):
    """Return a file:// url (as string) for the given pathlib.Path object.

    Arguments:
        path: The filepath as a Pathlib object
    """
    return urlutils.file_url(str(path))


class TestDirbrowserHtml:

    @dataclasses.dataclass
    class Parsed:

        parent: str
        folders: List[str]
        files: List[str]

    @dataclasses.dataclass
    class Item:

        link: str
        text: str

    @pytest.fixture
    def parser(self):
        """Provide a function to get a parsed dirbrowser document."""
        def parse(path):
            html = filescheme.dirbrowser_html(path).decode('utf-8')
            soup = bs4.BeautifulSoup(html, 'html.parser')

            with testutils.ignore_bs4_warning():
                print(soup.prettify())

            container = soup('div', id='dirbrowserContainer')[0]

            parent_elem = container('ul', class_='parent')
            if not parent_elem:
                parent = None
            else:
                parent = parent_elem[0].li.a.string

            folders = []
            files = []

            for li in container('ul', class_='folders')[0]('li'):
                item = self.Item(link=li.a['href'], text=str(li.a.string))
                folders.append(item)

            for li in container('ul', class_='files')[0]('li'):
                item = self.Item(link=li.a['href'], text=str(li.a.string))
                files.append(item)

            return self.Parsed(parent=parent, folders=folders, files=files)

        return parse

    def test_basic(self):
        html = filescheme.dirbrowser_html(pathlib.Path.cwd()).decode('utf-8')
        soup = bs4.BeautifulSoup(html, 'html.parser')

        with testutils.ignore_bs4_warning():
            print(soup.prettify())

        container = soup.div
        assert container['id'] == 'dirbrowserContainer'
        title_elem = container('div', id='dirbrowserTitle')[0]
        title_text = title_elem('p', id='dirbrowserTitleText')[0].text
        assert title_text == 'Browse directory: {}'.format(pathlib.Path.cwd())

    def test_icons(self, monkeypatch):
        """Make sure icon paths are correct file:// URLs."""
        html = filescheme.dirbrowser_html(pathlib.Path.cwd()).decode('utf-8')
        soup = bs4.BeautifulSoup(html, 'html.parser')

        with testutils.ignore_bs4_warning():
            print(soup.prettify())

        css = soup.html.head.style.string
        assert "background-image: url('qute://resource/img/folder.svg');" in css

    def test_empty(self, tmp_path, parser):
        parsed = parser(tmp_path)
        assert parsed.parent
        assert not parsed.folders
        assert not parsed.files

    def test_files(self, tmp_path, parser):
        foo_file = tmp_path / 'foo'
        bar_file = tmp_path / 'bar'
        foo_file.touch()
        bar_file.touch()

        parsed = parser(tmp_path)
        assert parsed.parent
        assert not parsed.folders
        foo_item = self.Item(_file_url(foo_file), str(foo_file.relative_to(tmp_path)))
        bar_item = self.Item(_file_url(bar_file), str(bar_file.relative_to(tmp_path)))
        assert parsed.files == [bar_item, foo_item]

    def test_html_special_chars(self, tmp_path, parser):
        special_file = tmp_path / 'foo&bar'
        special_file.touch()

        parsed = parser(tmp_path)
        item = self.Item(_file_url(special_file),
                         str(special_file.relative_to(tmp_path)))
        assert parsed.files == [item]

    def test_dirs(self, tmp_path, parser):
        foo_dir = tmp_path / 'foo'
        bar_dir = tmp_path / 'bar'
        foo_dir.mkdir()
        bar_dir.mkdir()

        parsed = parser(tmp_path)
        assert parsed.parent
        assert not parsed.files
        foo_item = self.Item(_file_url(foo_dir), str(foo_dir.relative_to(tmp_path)))
        bar_item = self.Item(_file_url(bar_dir), str(bar_dir.relative_to(tmp_path)))
        assert parsed.folders == [bar_item, foo_item]

    def test_mixed(self, tmp_path, parser):
        foo_file = tmp_path / 'foo'
        bar_dir = tmp_path / 'bar'
        foo_file.touch()
        bar_dir.mkdir()

        parsed = parser(tmp_path)
        foo_item = self.Item(_file_url(foo_file),
                             str(foo_file.relative_to(str(tmp_path))))
        bar_item = self.Item(_file_url(bar_dir),
                             str(bar_dir.relative_to(tmp_path)))
        assert parsed.parent
        assert parsed.files == [foo_item]
        assert parsed.folders == [bar_item]

    def test_root_dir(self, tmp_path, parser):
        root_dir = (pathlib.Path('C:\\')
        if utils.is_windows else pathlib.Path('/'))
        parsed = parser(root_dir)
        assert not parsed.parent

    def test_oserror(self, mocker):
        m = mocker.patch('qutebrowser.browser.webkit.network.filescheme.'
                         'pathlib.Path.iterdir')
        m.side_effect = OSError('Error message')
        html = filescheme.dirbrowser_html(pathlib.Path('')).decode('utf-8')
        soup = bs4.BeautifulSoup(html, 'html.parser')

        with testutils.ignore_bs4_warning():
            print(soup.prettify())

        error_msg = soup('p', id='error-message-text')[0].string
        assert error_msg == 'Error message'


class TestFileSchemeHandler:

    def test_dir(self, tmp_path):
        url = QUrl.fromLocalFile(str(tmp_path))
        req = QNetworkRequest(url)
        reply = filescheme.handler(req, None, None)
        tmpdir_path = tmp_path
        assert reply.readAll() == filescheme.dirbrowser_html(tmpdir_path)

    def test_file(self, tmp_path):
        filename = tmp_path / 'foo'
        filename.touch()
        url = QUrl.fromLocalFile(str(filename))
        req = QNetworkRequest(url)
        reply = filescheme.handler(req, None, None)
        assert reply is None

    def test_unicode_encode_error(self, mocker):
        url = QUrl('file:///tmp/foo')
        req = QNetworkRequest(url)

        err = UnicodeEncodeError('ascii', '', 0, 2, 'foo')
        mocker.patch('pathlib.Path.is_dir', side_effect=err)

        reply = filescheme.handler(req, None, None)
        assert reply is None
