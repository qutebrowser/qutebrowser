# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""The directory browser page."""

import os

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
    items = [{'name': filename, 'absname':
             os.path.abspath(os.path.join(basedir, filename))}
             for filename in all_files
             if filterfunc(os.path.join(basedir, filename))]
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
    html = template.render(title=title, url=urlstring, icon='', parent=parent,
                           files=files, directories=directories, folder=folder,
                           file=file)
    return html
