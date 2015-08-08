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

    folder = resource_filename('img/folder.png')
    file = resource_filename('img/file.png')

    def is_file(file):
        return os.path.isfile(os.path.join(urlstring, file))

    def is_dir(file):
        return os.path.isdir(os.path.join(urlstring, file))

    if os.path.dirname(urlstring) == urlstring:
        parent = None
    else:
        parent = os.path.dirname(urlstring)
    all_files = os.listdir(urlstring)
    files = sorted([{'name': file, 'absname': os.path.join(urlstring, file)}
                   for file in all_files if is_file(file)],
                   key=lambda v: v['name'].lower())
    directories = sorted([{'name': file, 'absname': os.path.join(urlstring,
                         file)}
                         for file in all_files if is_dir(file)],
                         key=lambda v: v['name'].lower())
    html = template.render(title=title, url=urlstring, icon='', parent=parent,
                           files=files, directories=directories, folder=folder,
                           file=file)
    return html
