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

import os
from urllib.parse import urljoin
from urllib.request import urlretrieve

from PyQt5.QtCore import QLibraryInfo

repository_url = 'https://redirector.gvt1.com/edgedl/chrome/dict/'


class Language:

    """Dictionary language specs."""

    def __init__(self, code, name, file):
        self.code = code
        self.name = name
        self.file = file

    @staticmethod
    def from_array(lang_array):
        """Create Language object from an array.

        Args:
            lang_array: an array of strings containing
                        the specs of the language in the following format:
                        [code, name, file]
        """
        return Language.from_tuple(tuple(lang_array))

    @staticmethod
    def from_tuple(lang_tuple):
        """Create Language object from a tuple.

        Args:
            lang_tuple: a tuple of strings containing
                        the specs of the language in the following format:
                        (code, name, file)
        """
        code, name, file = lang_tuple
        return Language(code, name, file)

    @staticmethod
    def from_tsv_string(tsv_string):
        """Create Language object from a string in tab-separated values format.

        Args:
            tsv_string: a string containing
                        the specs of the language in the following format:
                        "code   name    file"
        """
        lang_array = tsv_string.split('\t')
        return Language.from_array(lang_array)

    def __repr__(self):
        return 'Language({}, {}, {})'.format(self.code, self.name, self.file)


def get_dictionary_dir():
    """Return the path to the QtWebEngine's dictionaries directory."""
    return os.path.join(QLibraryInfo.location(QLibraryInfo.DataPath),
                        'qtwebengine_dictionaries')


def get_language_list_file():
    """Return the path to the file with the list of all available languages."""
    package_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(package_dir, 'langs.tsv')


def get_available_languages():
    """Return a list of Language objects of all available languages."""
    with open(get_language_list_file(), 'r', encoding='UTF-8') as file:
        return [Language.from_tsv_string(line[:-1]) for line in file]


def get_installed_languages():
    """Return a list of Language objects of all installed languages."""
    if not os.path.isdir(get_dictionary_dir()):
        return []
    installed_files = [os.path.basename(file)
                       for file in os.listdir(get_dictionary_dir())]
    all_languages = get_available_languages()
    return filter_languages(all_languages, installed_files,
                            by=lambda lang: lang.file,
                            fail_on_unknown=False)


def filter_languages(languages, selected, by=lambda lang: lang.code,
                     fail_on_unknown=True):
    """Filter a list of languages based on an inclusion list.

    Args:
        languages: a list of languages to filter
        selected: a list of keys to select
        by: a function returning the selection key (code by default)
        fail_on_unknown: whether to raise an error if there is an unknown
                         key in selected
    """
    filtered_languages = []
    for language in languages:
        if by(language) in selected:
            filtered_languages.append(language)
            selected.remove(by(language))
    if fail_on_unknown and selected:
        unknown = ', '.join(selected)
        raise ValueError('unknown languages found: {}'.format(unknown))
    return filtered_languages


def download_dictionary(url, dest):
    urlretrieve(url, dest)


def install(languages):
    """Install languages."""
    for lang in languages:
        try:
            print('Installing {}: {}'.format(lang.code, lang.name))
            lang_url = urljoin(repository_url, lang.file)
            if not os.path.isdir(get_dictionary_dir()):
                print('WARN: {} does not exist, creating the directory'.format(
                    get_dictionary_dir()))
                os.makedirs(get_dictionary_dir())
            print('Downloading {}'.format(lang_url))
            download_dictionary(lang_url, os.path.join(get_dictionary_dir(),
                                                       lang.file))
            print('Done.')
        except PermissionError as e:
            print(e)
