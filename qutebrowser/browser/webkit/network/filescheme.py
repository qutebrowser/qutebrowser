# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
#
# pylint complains when using .render() on jinja templates, so we make it shut
# up for this whole module.

"""Handler functions for file:... pages."""

import pathlib
from typing import List, Dict, Callable

from qutebrowser.browser.webkit.network import networkreply
from qutebrowser.utils import jinja


def get_file_list(
        basedir: pathlib.Path,
        all_files: List[pathlib.Path],
        filterfunc: Callable[[pathlib.Path], bool]
) -> List[Dict[str, str]]:
    """Get a list of files filtered by a filter function and sorted by name.

    Args:
        basedir: The parent directory of all files.
        all_files: The list of files to filter and sort.
        filterfunc: The filter function.

    Return:
        A list of dicts. Each dict contains the name and absname keys.
    """
    items = []
    for filename in all_files:
        absname = basedir / filename
        if filterfunc(absname):
            items.append({'name': filename.name, 'absname': str(absname)})
    return sorted(items, key=lambda v: v['name'].lower())


def is_root(directory: pathlib.Path) -> bool:
    """Check if the directory is the root directory.

    Args:
        directory: The directory to check.

    Return:
        Whether the directory is a root directory or not.
    """
    return not directory.parents


def dirbrowser_html(path: pathlib.Path) -> bytes:
    """Get the directory browser web page.

    Args:
        path: The directory path.

    Return:
        The HTML of the web page.
    """
    title = "Browse directory: {}".format(path)

    if is_root(path):
        parent = None
    else:
        parent = str(path.parent)

    try:
        all_files = list(path.iterdir())
    except OSError as e:
        html = jinja.render('error.html',
                            title="Error while reading directory",
                            url='file:///{}'.format(path), error=str(e))
        return html.encode('UTF-8', errors='xmlcharrefreplace')

    files = get_file_list(path, all_files, pathlib.Path.is_file)
    directories = get_file_list(path, all_files, pathlib.Path.is_dir)
    html = jinja.render('dirbrowser.html', title=title, url=str(path),
                        parent=parent, files=files, directories=directories)
    return html.encode('UTF-8', errors='xmlcharrefreplace')


def handler(request, _operation, _current_url):
    """Handler for a file:// URL.

    Args:
        request: QNetworkRequest to answer to.
        _operation: The HTTP operation being done.
        _current_url: The page we're on currently.

    Return:
        A QNetworkReply for directories, None for files.
    """
    path = pathlib.Path(request.url().toLocalFile())
    try:
        if path.is_dir():
            data = dirbrowser_html(path)
            return networkreply.FixedDataNetworkReply(
                request, data, 'text/html')
        return None
    except UnicodeEncodeError:
        return None
