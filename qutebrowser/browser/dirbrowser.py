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


def dirbrowser(url):
    """Get the directory browser web page.

    Args:
        url: The directory path.

    Return:
        The HTML of the web page.
    """
    title = "Browse directory: {}".format(url)
    template = jinja.env.get_template('dirbrowser.html')
    # pylint: disable=no-member
    # https://bitbucket.org/logilab/pylint/issue/490/

    def is_file(file):
        return os.path.isfile(os.path.join(url, file))

    def is_dir(file):
        return os.path.isdir(os.path.join(url, file))

    parent = os.path.dirname(url)
    all_files = os.listdir(url)
    files = sorted([(file, os.path.join(url, file)) for file in all_files if
                    is_file(file)])
    directories = sorted([(file, os.path.join(url, file)) for file in
                          all_files if is_dir(file)])
    html = template.render(title=title, url=url, icon='', parent=parent,
                           files=files, directories=directories)
    return html
