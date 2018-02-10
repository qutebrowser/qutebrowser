# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2018 Michal Siedlaczek <michal.siedlaczek@gmail.com>

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
import re

from PyQt5.QtCore import QLibraryInfo
from qutebrowser.utils import log


def version(filename):
    """Extract the version number from the dictionary file name."""
    version_re = re.compile(r".+-(?P<version>[0-9]+-[0-9]+?)\.bdic")
    match = version_re.fullmatch(filename)
    if match is None:
        raise ValueError('the given dictionary file name is malformed: {}'
                         .format(filename))
    return tuple(int(n) for n in match.group('version').split('-'))


def dictionary_dir():
    """Return the path (str) to the QtWebEngine's dictionaries directory."""
    datapath = QLibraryInfo.location(QLibraryInfo.DataPath)
    return os.path.join(datapath, 'qtwebengine_dictionaries')


def local_files(code):
    """Return all installed dictionaries for the given code."""
    pathname = os.path.join(dictionary_dir(), '{}*.bdic'.format(code))
    matching_dicts = glob.glob(pathname)
    files = []
    for matching_dict in sorted(matching_dicts, key=version, reverse=True):
        filename = os.path.basename(matching_dict)
        log.config.debug('Found file for dict {}: {}'.format(code, filename))
        files.append(filename)
    return files


def local_filename(code):
    """Return the newest installed dictionary for the given code.

    Return the filename of the installed dictionary with the highest version
    number or None if the dictionary is not installed.
    """
    all_installed = local_files(code)
    return os.path.splitext(all_installed[0])[0] if all_installed else None
