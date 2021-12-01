# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015-2018 Daniel Schadt
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

"""Test the built-in directory browser."""

import pathlib
import dataclasses
from typing import List

import pytest
import bs4

from PyQt5.QtCore import QUrl

from qutebrowser.utils import urlutils
from helpers import testutils


pytestmark = pytest.mark.qtwebengine_skip("Title is empty when parsing for "
                                          "some reason?")


class DirLayout:

    """Provide a fake directory layout to test dirbrowser."""

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
            path = self.layout / filename
            path.parent.mkdir(exist_ok=True, parents=True)
            path.touch()

    def file_url(self):
        """Return a file:// link to the directory."""
        return urlutils.file_url(str(self.layout))

    def path(self, *parts):
        """Return the path to the given file inside the layout folder."""
        return self.layout.joinpath(*parts)

    def base_path(self):
        """Return the path of the base temporary folder."""
        return self.base


@dataclasses.dataclass
class Parsed:

    path: str
    parent: str
    folders: List[str]
    files: List[str]


@dataclasses.dataclass
class Item:

    path: str
    link: str
    text: str


def parse(quteproc):
    """Parse the dirbrowser content from the given quteproc.

    Args:
        quteproc: The quteproc fixture.
    """
    html = quteproc.get_content(plain=False)
    soup = bs4.BeautifulSoup(html, 'html.parser')

    with testutils.ignore_bs4_warning():
        print(soup.prettify())

    title_prefix = 'Browse directory: '
    # Strip off the title prefix to obtain the path of the folder that
    # we're browsing
    path = pathlib.Path(soup.title.string[len(title_prefix):])

    container = soup('div', id='dirbrowserContainer')[0]

    parent_elem = container('ul', class_='parent')
    if not parent_elem:
        parent = None
    else:
        parent = pathlib.Path(QUrl(parent_elem[0].li.a['href']).toLocalFile())

    folders = []
    files = []

    for css_class, list_ in [('folders', folders), ('files', files)]:
        for li in container('ul', class_=css_class)[0]('li'):
            item_path = pathlib.Path(QUrl(li.a['href']).toLocalFile())
            list_.append(Item(path=item_path, link=li.a['href'],
                              text=str(li.a.string)))

    return Parsed(path=path, parent=parent, folders=folders, files=files)


@pytest.fixture(scope='module')
def dir_layout(tmp_path_factory):
    return DirLayout(tmp_path_factory)


def test_parent_folder(dir_layout, quteproc):
    quteproc.open_url(dir_layout.file_url())
    page = parse(quteproc)
    assert page.parent == dir_layout.base_path()


def test_parent_with_slash(dir_layout, quteproc):
    """Test the parent link with a URL that has a trailing slash."""
    quteproc.open_url(dir_layout.file_url() + '/')
    page = parse(quteproc)
    assert page.parent == dir_layout.base_path()


def test_parent_in_root_dir(dir_layout, quteproc):
    # This actually works on windows
    urlstr = urlutils.file_url(str(pathlib.Path('/')))
    quteproc.open_url(urlstr)
    page = parse(quteproc)
    assert page.parent is None


def test_enter_folder_smoke(dir_layout, quteproc):
    quteproc.open_url(dir_layout.file_url())
    quteproc.send_cmd(':hint all normal')
    # a is the parent link, s is the first listed folder/file
    quteproc.send_cmd(':hint-follow s')
    expected_url = urlutils.file_url(str(dir_layout.path('folder0')))
    quteproc.wait_for_load_finished_url(expected_url)
    page = parse(quteproc)
    assert page.path == dir_layout.path('folder0')


@pytest.mark.parametrize('folder', DirLayout.layout_folders())
def test_enter_folder(dir_layout, quteproc, folder):
    quteproc.open_url(dir_layout.file_url())
    quteproc.click_element_by_text(text=folder)
    expected_url = urlutils.file_url(str(dir_layout.path(folder)))
    quteproc.wait_for_load_finished_url(expected_url)
    page = parse(quteproc)
    assert page.path == dir_layout.path(folder)
    assert page.parent == dir_layout.path()
    folders, files = DirLayout.get_folder_content(folder)
    foldernames = [item.text for item in page.folders]
    assert foldernames == folders
    filenames = [item.text for item in page.files]
    assert filenames == files
