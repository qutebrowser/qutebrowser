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
import base64
import json
import sys
import urllib.request
import functools
import io
import attr

from PyQt5.QtCore import QLibraryInfo, QVersionNumber, QUrl
from qutebrowser.utils import objreg, log, standarddir
from qutebrowser.config import config, configdata
from qutebrowser.browser import downloads

@attr.s
class Language:

    """Dictionary language specs."""

    code = attr.ib()
    name = attr.ib()
    remote_filename = attr.ib()
    local_filename = attr.ib(default=None)
    _file_extension = attr.ib('bdic', init=False)

    def __attrs_post_init__(self):
        if self.local_filename is None:
            self.local_filename = local_filename(self.code)

    @property
    def remote_path(self):
        """Resolve the filename with extension the remote dictionary."""
        return '.'.join([self.remote_filename, self._file_extension])

    @property
    def local_path(self):
        """Resolve the filename with extension the local dictionary."""
        if self.local_filename is None:
            return None
        return '.'.join([self.local_filename, self._file_extension])

    @property
    def remote_version(self):
        """Resolve the version of the local dictionary."""
        return version(self.remote_path)

    @property
    def local_version(self):
        """Resolve the version of the local dictionary."""
        local_path = self.local_path
        if local_path is None:
            return None
        return version(local_path)


class Installer:

    """Download and install dictionaries asynchronously."""

    def __init__(self, profile, completed, codes):
        self.api_url = 'https://chromium.googlesource.com/chromium/deps/hunspell_dictionaries.git/+/master/'
        self._download_manager = objreg.get('qtnetwork-download-manager')
        self._in_progress = []
        self._profile = profile
        self._completed = completed

        if not codes:
            return self.load_dictionaries()

        if not os.path.isdir(dictionary_dir()):
            msg = '{} does not exist, creating the directory'
            log.config.debug(msg.format(dictionary_dir()))
            os.makedirs(dictionary_dir())

        for code in codes:
            for language in self.available_langs():
                if language.code == code:
                    self.install_language(language)

    def available_langs(self):
        """Return a list of Language objects of all available languages."""

        option = configdata.DATA['spellcheck.languages']
        lang_map = option.typ.valtype.valid_values.descriptions

        api_list = self.lang_list_from_api()
        code2file = {}
        for code, filename in api_list:
            if latest_yet(code2file, code, filename):
                code2file[code] = filename
        return [
            Language(code, name, code2file[code])
            for code, name in lang_map.items()
            if code in code2file
        ]

    def lang_list_from_api(self):
        """Return a JSON with a list of available languages from Google API."""
        listurl = self.api_url + '?format=JSON'
        response = urllib.request.urlopen(listurl)
        # A special 5-byte prefix must be stripped from the response content
        # See: https://github.com/google/gitiles/issues/22
        #      https://github.com/google/gitiles/issues/82
        json_content = response.read()[5:]
        entries = json.loads(json_content.decode('utf-8'))['entries']
        parsed_entries = [parse_entry(entry) for entry in entries]
        return [entry for entry in parsed_entries if entry is not None]

    def install_language(self, lang):
        """Install a language given by the argument."""
        log.config.info('Installing dictionary {}: {}'.format(
            lang.code, lang.name))
        lang_url = self.api_url + lang.remote_path + '?format=TEXT'
        log.config.debug('Downloading {}'.format(lang_url))
        dest = os.path.join(dictionary_dir(), lang.remote_path)
        self.download_dictionary(lang_url, dest, lang.code)

    def download_dictionary(self, url, dest, code):
        """Download a decoded dictionary file."""
        fobj = io.BytesIO()
        fobj.name = 'dictionary: ' + code
        target = downloads.FileObjDownloadTarget(fobj)
        download = self._download_manager.get(
            QUrl(url), target=target, auto_remove=True)
        self._in_progress.append(download)
        download.finished.connect(
            functools.partial(self.write_dictionary, download, dest))

    def write_dictionary(self, download, dest):
        """Check if download is finished and if so write it to file."""
        self._in_progress.remove(download)
        if download.successful:
            try:
                download.fileobj.seek(0)
                decoded = base64.decodebytes(download.fileobj.read())
                with open(dest, 'bw') as dict_file:
                    dict_file.write(decoded)
            except Exception as e:
                log.config.error('Failed to save dictionary: ' + str(e))
            finally:
                download.fileobj.close()
                self._completed.append(dest)
                log.config.debug('Done.')

    def load_dictionaries(self):
        """Load installed dictionaries into current profile."""
        if not self._in_progress:
            self._profile.setSpellCheckLanguages(self._completed)


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
    if QLibraryInfo.version() <= QVersionNumber(5, 10):
        datapath = QLibraryInfo.location(QLibraryInfo.DataPath)
        return os.path.join(datapath, 'qtwebengine_dictionaries')

    return os.path.join(standarddir.data(), 'dictionaries')


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


def parse_entry(entry):
    """Parse an entry from the remote API."""
    dict_re = re.compile(r"""
        (?P<filename>(?P<code>[a-z]{2}(-[A-Z]{2})?).*)\.bdic
    """, re.VERBOSE)
    match = dict_re.fullmatch(entry['name'])
    if match is not None:
        return match.group('code'), match.group('filename')
    else:
        return None


def latest_yet(code2file, code, filename):
    """Determine whether the latest version so far."""
    if code not in code2file:
        return True
    return version(code2file[code]) < version(filename)


def init(profile, install=True):
    """Initilialise spellcheking."""
    available, missing = [], []
    for code in config.val.spellcheck.languages or []:
        if local_filename(code):
            available.append(code)
        else:
            missing.append(code)
    Installer(profile, available, missing)
