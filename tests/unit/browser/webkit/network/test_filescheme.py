# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

import os

import attr
import pytest
import bs4
from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QNetworkRequest

from qutebrowser.browser.webkit.network import filescheme
from qutebrowser.utils import urlutils, utils
from helpers import utils as testutils


@pytest.mark.parametrize('create_file, create_dir, filterfunc, expected', [
    (True, False, os.path.isfile, True),
    (True, False, os.path.isdir, False),

    (False, True, os.path.isfile, False),
    (False, True, os.path.isdir, True),

    (False, False, os.path.isfile, False),
    (False, False, os.path.isdir, False),
])
def test_get_file_list(tmpdir, create_file, create_dir, filterfunc, expected):
    """Test get_file_list."""
    path = tmpdir / 'foo'
    if create_file or create_dir:
        path.ensure(dir=create_dir)

    all_files = os.listdir(str(tmpdir))

    result = filescheme.get_file_list(str(tmpdir), all_files, filterfunc)
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
        assert filescheme.is_root(directory) == is_root

    @pytest.mark.posix
    @pytest.mark.parametrize('directory, is_root', [
        ('/foo/bar', False),
        ('/foo/', False),
        ('/foo', False),
        ('/', True)
    ])
    def test_posix(self, directory, is_root):
        assert filescheme.is_root(directory) == is_root


class TestParentDir:

    @pytest.mark.windows
    @pytest.mark.parametrize('directory, parent', [
        ('C:\\foo\\bar', 'C:\\foo'),
        ('C:\\foo', 'C:\\'),
        ('C:\\foo\\', 'C:\\'),
        ('C:\\', 'C:\\'),
    ])
    def test_windows(self, directory, parent):
        assert filescheme.parent_dir(directory) == parent

    @pytest.mark.posix
    @pytest.mark.parametrize('directory, parent', [
        ('/home/foo', '/home'),
        ('/home', '/'),
        ('/home/', '/'),
        ('/', '/'),
    ])
    def test_posix(self, directory, parent):
        assert filescheme.parent_dir(directory) == parent


def _file_url(path):
    """Return a file:// url (as string) for the given LocalPath.

    Arguments:
        path: The filepath as LocalPath (as handled by py.path)
    """
    return urlutils.file_url(str(path))


class TestDirbrowserHtml:

    @attr.s
    class Parsed:

        parent = attr.ib()
        folders = attr.ib()
        files = attr.ib()

    @attr.s
    class Item:

        link = attr.ib()
        text = attr.ib()

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
        html = filescheme.dirbrowser_html(os.getcwd()).decode('utf-8')
        soup = bs4.BeautifulSoup(html, 'html.parser')

        with testutils.ignore_bs4_warning():
            print(soup.prettify())

        container = soup.div
        assert container['id'] == 'dirbrowserContainer'
        title_elem = container('div', id='dirbrowserTitle')[0]
        title_text = title_elem('p', id='dirbrowserTitleText')[0].text
        assert title_text == 'Browse directory: {}'.format(os.getcwd())

    def test_icons(self, monkeypatch):
        """Make sure icon paths are correct file:// URLs."""
        monkeypatch.setattr(filescheme.jinja.utils, 'resource_filename',
                            lambda name: '/test path/foo.svg')

        html = filescheme.dirbrowser_html(os.getcwd()).decode('utf-8')
        soup = bs4.BeautifulSoup(html, 'html.parser')

        with testutils.ignore_bs4_warning():
            print(soup.prettify())

        css = soup.html.head.style.string
        assert "background-image: url('file:///test%20path/foo.svg');" in css

    def test_empty(self, tmpdir, parser):
        parsed = parser(str(tmpdir))
        assert parsed.parent
        assert not parsed.folders
        assert not parsed.files

    def test_files(self, tmpdir, parser):
        foo_file = tmpdir / 'foo'
        bar_file = tmpdir / 'bar'
        foo_file.ensure()
        bar_file.ensure()

        parsed = parser(str(tmpdir))
        assert parsed.parent
        assert not parsed.folders
        foo_item = self.Item(_file_url(foo_file), foo_file.relto(tmpdir))
        bar_item = self.Item(_file_url(bar_file), bar_file.relto(tmpdir))
        assert parsed.files == [bar_item, foo_item]

    def test_html_special_chars(self, tmpdir, parser):
        special_file = tmpdir / 'foo&bar'
        special_file.ensure()

        parsed = parser(str(tmpdir))
        item = self.Item(_file_url(special_file), special_file.relto(tmpdir))
        assert parsed.files == [item]

    def test_dirs(self, tmpdir, parser):
        foo_dir = tmpdir / 'foo'
        bar_dir = tmpdir / 'bar'
        foo_dir.ensure(dir=True)
        bar_dir.ensure(dir=True)

        parsed = parser(str(tmpdir))
        assert parsed.parent
        assert not parsed.files
        foo_item = self.Item(_file_url(foo_dir), foo_dir.relto(tmpdir))
        bar_item = self.Item(_file_url(bar_dir), bar_dir.relto(tmpdir))
        assert parsed.folders == [bar_item, foo_item]

    def test_mixed(self, tmpdir, parser):
        foo_file = tmpdir / 'foo'
        bar_dir = tmpdir / 'bar'
        foo_file.ensure()
        bar_dir.ensure(dir=True)

        parsed = parser(str(tmpdir))
        foo_item = self.Item(_file_url(foo_file), foo_file.relto(tmpdir))
        bar_item = self.Item(_file_url(bar_dir), bar_dir.relto(tmpdir))
        assert parsed.parent
        assert parsed.files == [foo_item]
        assert parsed.folders == [bar_item]

    def test_root_dir(self, tmpdir, parser):
        root_dir = 'C:\\' if utils.is_windows else '/'
        parsed = parser(root_dir)
        assert not parsed.parent

    def test_oserror(self, mocker):
        m = mocker.patch('qutebrowser.browser.webkit.network.filescheme.'
                         'os.listdir')
        m.side_effect = OSError('Error message')
        html = filescheme.dirbrowser_html('').decode('utf-8')
        soup = bs4.BeautifulSoup(html, 'html.parser')

        with testutils.ignore_bs4_warning():
            print(soup.prettify())

        error_msg = soup('p', id='error-message-text')[0].string
        assert error_msg == 'Error message'


class TestFileSchemeHandler:

    def test_dir(self, tmpdir):
        url = QUrl.fromLocalFile(str(tmpdir))
        req = QNetworkRequest(url)
        reply = filescheme.handler(req, None, None)
        # The URL will always use /, even on Windows - so we force this here
        # too.
        tmpdir_path = str(tmpdir).replace(os.sep, '/')
        assert reply.readAll() == filescheme.dirbrowser_html(tmpdir_path)

    def test_file(self, tmpdir):
        filename = tmpdir / 'foo'
        filename.ensure()
        url = QUrl.fromLocalFile(str(filename))
        req = QNetworkRequest(url)
        reply = filescheme.handler(req, None, None)
        assert reply is None

    def test_unicode_encode_error(self, mocker):
        url = QUrl('file:///tmp/foo')
        req = QNetworkRequest(url)

        err = UnicodeEncodeError('ascii', '', 0, 2, 'foo')
        mocker.patch('os.path.isdir', side_effect=err)

        reply = filescheme.handler(req, None, None)
        assert reply is None
