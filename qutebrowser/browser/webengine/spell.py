# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import os.path
import re
import shutil

from PyQt5.QtCore import QLibraryInfo
from qutebrowser.utils import log, message, standarddir, qtutils

dict_version_re = re.compile(r".+-(?P<version>[0-9]+-[0-9]+?)\.bdic")


def version(filename):
    """Extract the version number from the dictionary file name."""
    match = dict_version_re.match(filename)
    if match is None:
        message.warning(
            "Found a dictionary with a malformed name: {}".format(filename))
        return None
    return tuple(int(n) for n in match.group('version').split('-'))


def dictionary_dir(old=False):
    """Return the path (str) to the QtWebEngine's dictionaries directory."""
    if qtutils.version_check('5.10', compiled=False) and not old:
        datapath = standarddir.data()
    else:
        datapath = QLibraryInfo.location(QLibraryInfo.DataPath)
    return os.path.join(datapath, 'qtwebengine_dictionaries')


def local_files(code):
    """Return all installed dictionaries for the given code.

    The returned dictionaries are sorted by version, therefore the latest will
    be the first element. The list will be empty if no dictionaries are found.
    """
    pathname = os.path.join(dictionary_dir(), '{}*.bdic'.format(code))
    matching_dicts = glob.glob(pathname)
    versioned_dicts = []
    for matching_dict in matching_dicts:
        parsed_version = version(matching_dict)
        if parsed_version is not None:
            filename = os.path.basename(matching_dict)
            log.config.debug('Found file for dict {}: {}'
                             .format(code, filename))
            versioned_dicts.append((parsed_version, filename))
    return [filename for version, filename
            in sorted(versioned_dicts, reverse=True)]


def local_filename(code):
    """Return the newest installed dictionary for the given code.

    Return the filename of the installed dictionary with the highest version
    number or None if the dictionary is not installed.
    """
    all_installed = local_files(code)
    return os.path.splitext(all_installed[0])[0] if all_installed else None


def init():
    """Initialize the dictionary path if supported."""
    if qtutils.version_check('5.10', compiled=False):
        new_dir = dictionary_dir()
        old_dir = dictionary_dir(old=True)
        os.environ['QTWEBENGINE_DICTIONARIES_PATH'] = new_dir
        try:
            if os.path.exists(old_dir) and not os.path.exists(new_dir):
                shutil.copytree(old_dir, new_dir)
        except OSError:
            log.misc.exception("Failed to copy old dictionaries")
