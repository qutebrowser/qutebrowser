# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=no-member
# https://bitbucket.org/logilab/pylint/issue/490/

"""Handler functions for different qute:... pages.

Module attributes:
    pyeval_output: The output of the last :pyeval command.
"""

import os

from qutebrowser.browser.network import schemehandler, networkreply
from qutebrowser.utils import jinja
from qutebrowser.utils.utils import resource_filename


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


def dirbrowser(urlstring):
    """Get the directory browser web page.

    Args:
        urlstring: The directory path.

    Return:
        The HTML of the web page.
    """
    title = "Browse directory: {}".format(urlstring)
    template = jinja.env.get_template('dirbrowser.html')
    # pylint: disable=no-member
    # https://bitbucket.org/logilab/pylint/issue/490/

    folder = resource_filename('img/folder.svg')
    file = resource_filename('img/file.svg')

    if os.path.dirname(urlstring) == urlstring:
        parent = None
    else:
        parent = os.path.dirname(urlstring)
    all_files = os.listdir(urlstring)
    files = get_file_list(urlstring, all_files, os.path.isfile)
    directories = get_file_list(urlstring, all_files, os.path.isdir)
    html = template.render(title=title, url=urlstring, icon='',
                           parent=parent, files=files,
                           directories=directories, folder=folder,
                           file=file)
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
            A QNetworkReply.
        """
        urlstring = request.url().toLocalFile()
        if os.path.isdir(urlstring) and os.access(urlstring, os.R_OK):
            data = dirbrowser(urlstring)
            return networkreply.FixedDataNetworkReply(
                request, data, 'text/html', self.parent())
