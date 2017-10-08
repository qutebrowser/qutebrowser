# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Michal Siedlaczek <michal.siedlaczek@gmail.com>

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

"""Installing and configuring spell-checking for QtWebEngine."""

import glob
import os

from PyQt5.QtCore import QLibraryInfo


def dictionary_dir():
    """Return the path (str) to the QtWebEngine's dictionaries directory."""
    datapath = QLibraryInfo.location(QLibraryInfo.DataPath)
    return os.path.join(datapath, 'qtwebengine_dictionaries')


def installed_file(code):
    """Return the installed dictionary for the given code.

    Return the filename of the installed dictionary or None
    if the dictionary is not installed.
    """
    pathname = os.path.join(dictionary_dir(), '{}*.bdic'.format(code))
    matching_dicts = glob.glob(pathname)
    if matching_dicts:
        with_extension = os.path.basename(matching_dicts[0])
        return os.path.splitext(with_extension)[0]
    else:
        return None
