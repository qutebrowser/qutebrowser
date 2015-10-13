# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015 Antoni Boucher (antoyo) <bouanto@zoho.com>
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
#
# pylint complains when using .render() on jinja templates, so we make it shut
# up for this whole module.

"""Handler functions for file:... pages."""

import os

from PyQt5.QtCore import QUrl

from qutebrowser.browser.network import schemehandler, networkreply
from qutebrowser.utils import utils, jinja


def get_file_list(basedir, all_files, filterfunc):
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
        absname = os.path.join(basedir, filename)
        if filterfunc(absname):
            items.append({'name': filename, 'absname': absname})
    return sorted(items, key=lambda v: v['name'].lower())


def is_root(directory):
    """Check if the directory is the root directory.

    Args:
        directory: The directory to check.

    Return:
        Whether the directory is a root directory or not.
    """
    return os.path.dirname(directory) == directory


def dirbrowser_html(path):
    """Get the directory browser web page.

    Args:
        path: The directory path.

    Return:
        The HTML of the web page.
    """
    title = "Browse directory: {}".format(path)
    template = jinja.env.get_template('dirbrowser.html')
    # pylint: disable=no-member
    # https://bitbucket.org/logilab/pylint/issue/490/

    folder_icon = utils.resource_filename('img/folder.svg')
    file_icon = utils.resource_filename('img/file.svg')

    folder_url = QUrl.fromLocalFile(folder_icon).toString(QUrl.FullyEncoded)
    file_url = QUrl.fromLocalFile(file_icon).toString(QUrl.FullyEncoded)

    if is_root(path):
        parent = None
    else:
        parent = os.path.dirname(path)

    try:
        all_files = os.listdir(path)
    except OSError as e:
        html = jinja.env.get_template('error.html').render(
            title="Error while reading directory",
            url='file://%s' % path,
            error=str(e),
            icon='')
        return html.encode('UTF-8', errors='xmlcharrefreplace')

    files = get_file_list(path, all_files, os.path.isfile)
    directories = get_file_list(path, all_files, os.path.isdir)
    html = template.render(title=title, url=path, icon='',
                           parent=parent, files=files,
                           directories=directories, folder_url=folder_url,
                           file_url=file_url)
    return html.encode('UTF-8', errors='xmlcharrefreplace')


class FileSchemeHandler(schemehandler.SchemeHandler):

    """Scheme handler for file: URLs."""

    def createRequest(self, _op, request, _outgoing_data):
        """Create a new request.

        Args:
             request: const QNetworkRequest & req
             _op: Operation op
             _outgoing_data: QIODevice * outgoingData

        Return:
            A QNetworkReply for directories, None for files.
        """
        path = request.url().toLocalFile()
        if os.path.isdir(path):
            data = dirbrowser_html(path)
            return networkreply.FixedDataNetworkReply(
                request, data, 'text/html', self.parent())
