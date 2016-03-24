# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Daniel Schadt
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

"""Test the built-in directory browser."""

import bs4
import collections

import pytest

from PyQt5.QtCore import QUrl
from qutebrowser.utils import jinja


class DirLayout:

    """Provide a fake directory layout to test dirbrowser."""

    Parsed = collections.namedtuple('Parsed', 'path, parent, folders, files')
    Item = collections.namedtuple('Item', 'path, link, text')

    LAYOUT = [
        'folder0/file00',
        'folder0/file01',
        'folder1/folder10/file100',
        'folder1/file10',
        'folder1/file11',
        'file0',
        'file1',
    ]

    @classmethod
    def layout_folders(cls):
        """Return all folders in the root directory of the layout."""
        folders = set()
        for path in cls.LAYOUT:
            parts = path.split('/')
            if len(parts) > 1:
                folders.add(parts[0])
        folders = list(folders)
        folders.sort()
        return folders

    @classmethod
    def get_folder_content(cls, name):
        """Return (folders, files) for the given folder in the root dir."""
        folders = set()
        files = set()
        for path in cls.LAYOUT:
            if not path.startswith(name + '/'):
                continue
            parts = path.split('/')
            if len(parts) == 2:
                files.add(parts[1])
            else:
                folders.add(parts[1])
        folders = list(folders)
        folders.sort()
        files = list(files)
        files.sort()
        return (folders, files)

    def __init__(self, factory):
        self._factory = factory
        self.base = factory.getbasetemp()
        self.layout = factory.mktemp('layout')
        self._mklayout()

    def _mklayout(self):
        for filename in self.LAYOUT:
            self.layout.ensure(filename)

    def file_url(self):
        """Return a file:// link to the directory."""
        return jinja.file_url(str(self.layout))

    def path(self, *parts):
        """Return the path to the given file inside the layout folder."""
        return str(self.layout.join(*parts))

    def parse(self, quteproc):
        """Parse the dirbrowser content from the given quteproc.

        Args:
            quteproc: The quteproc fixture.
        """
        html = quteproc.get_content(plain=False)
        soup = bs4.BeautifulSoup(html, 'html.parser')
        print(soup.prettify())
        title_prefix = 'Browse directory: '
        # Strip off the title prefix to obtain the path of the folder that
        # we're browsing
        path = soup.title.string[len(title_prefix):]

        container = soup('div', id='dirbrowserContainer')[0]

        parent_elem = container('ul', class_='parent')
        if len(parent_elem) == 0:
            parent = None
        else:
            parent = QUrl(parent_elem[0].li.a['href']).toLocalFile()

        folders = []
        files = []

        for css_class, list_ in [('folders', folders), ('files', files)]:
            for li in container('ul', class_=css_class)[0]('li'):
                item_path = QUrl(li.a['href']).toLocalFile()
                list_.append(self.Item(path=item_path, link=li.a['href'],
                                       text=str(li.a.string)))

        return self.Parsed(path=path, parent=parent, folders=folders,
                           files=files)


@pytest.fixture(scope='module')
def dir_layout(tmpdir_factory):
    return DirLayout(tmpdir_factory)


def test_parent_folder(dir_layout, quteproc):
    quteproc.open_url(dir_layout.file_url())
    page = dir_layout.parse(quteproc)
    assert page.parent == str(dir_layout.base)


def test_parent_with_slash(dir_layout, quteproc):
    """Test the parent link with an URL that has a trailing slash."""
    quteproc.open_url(dir_layout.file_url() + '/')
    page = dir_layout.parse(quteproc)
    assert page.parent == str(dir_layout.base)


def test_enter_folder_smoke(dir_layout, quteproc):
    quteproc.open_url(dir_layout.file_url())
    quteproc.send_cmd(':hint all normal')
    # a is the parent link, s is the first listed folder/file
    quteproc.send_cmd(':follow-hint s')
    page = dir_layout.parse(quteproc)
    assert page.path == dir_layout.path('folder0')


@pytest.mark.parametrize('folder', DirLayout.layout_folders())
def test_enter_folder(dir_layout, quteproc, folder):
    quteproc.open_url(dir_layout.file_url())
    # Use Javascript and XPath to click the link that has the folder name as
    # text.
    quteproc.send_cmd(
        ':jseval document.evaluate(\'//a[text()="{}"]\', document, null, '
        'XPathResult.ANY_TYPE, null).iterateNext().click()'
        .format(folder)
    )
    page = dir_layout.parse(quteproc)
    assert page.path == dir_layout.path(folder)
    assert page.parent == dir_layout.path()
    folders, files = DirLayout.get_folder_content(folder)
    foldernames = [item.text for item in page.folders]
    assert foldernames == folders
    filenames = [item.text for item in page.files]
    assert filenames == files
