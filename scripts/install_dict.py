#!/usr/bin/env python3
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

"""A script installing Hunspell dictionaries.

Use: python -m scripts.install_dict [--list] [lang [lang [...]]]
"""

import argparse
import base64
import json
import os
import sys
import re
import urllib.request

import attr

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
from qutebrowser.browser.webengine import spell
from qutebrowser.config import configdata


API_URL = 'https://chromium.googlesource.com/chromium/deps/hunspell_dictionaries.git/+/master/'


class InvalidLanguageError(Exception):

    """Raised when requesting invalid languages."""

    def __init__(self, invalid_langs):
        msg = 'invalid languages: {}'.format(', '.join(invalid_langs))
        super().__init__(msg)


@attr.s
class Language:

    """Dictionary language specs."""

    code = attr.ib(None)
    name = attr.ib(None)
    file_basename = attr.ib(None)
    file_extension = attr.ib('bdic')

    @property
    def file_path(self):
        return '.'.join([self.file_basename, self.file_extension])


def get_argparser():
    """Get the argparse parser."""
    desc = 'Install Hunspell dictionaries for QtWebEngine.'
    parser = argparse.ArgumentParser(prog='install_dict',
                                     description=desc)
    parser.add_argument('-l', '--list', action='store_true',
                        help="Display the list of available languages.")
    parser.add_argument('languages', nargs='*',
                        help="A list of languages to install.")
    return parser


def print_list(languages):
    for lang in languages:
        print(lang.code, lang.name, sep='\t')


def valid_languages():
    """Return a mapping from valid language codes to their names."""
    option = configdata.DATA['spellcheck.languages']
    return option.typ.valtype.valid_values.descriptions


def language_list_from_api():
    """Return a JSON with a list of available languages from Google API."""
    listurl = API_URL + '?format=JSON'
    response = urllib.request.urlopen(listurl)
    # A special 5-byte prefix must be stripped from the response content
    # See: https://github.com/google/gitiles/issues/22
    #      https://github.com/google/gitiles/issues/82
    json_content = response.read()[5:]
    entries = json.loads(json_content.decode('utf-8'))['entries']
    return entries


def available_languages():
    """Return a list of Language objects of all available languages."""
    lang_map = valid_languages()
    api_list = language_list_from_api()
    dict_re = re.compile(r"""
        (?P<filename>(?P<dict>[a-z]{2}(-[A-Z]{2})?).*)\.bdic
    """, re.VERBOSE)
    code2file = {}
    for lang in api_list:
        match = dict_re.match(lang['name'])
        if match is not None:
            code2file[match.group('dict')] = match.group('filename')
    return [
        Language(code, name, code2file[code])
        for code, name in lang_map.items()
    ]


def download_dictionary(url, dest):
    """Download a decoded dictionary file."""
    response = urllib.request.urlopen(url)
    decoded = base64.decodebytes(response.read())
    with open(dest, 'bw') as dict_file:
        dict_file.write(decoded)


def filter_languages(languages, selected):
    """Filter a list of languages based on an inclusion list.

    Args:
        languages: a list of languages to filter
        selected: a list of keys to select
    """
    filtered_languages = []
    for language in languages:
        if language.code in selected:
            filtered_languages.append(language)
            selected.remove(language.code)
    if selected:
        raise InvalidLanguageError(selected)
    return filtered_languages


def install_lang(lang):
    """Install a single lang given by the argument."""
    print('Installing {}: {}'.format(lang.code, lang.name))
    lang_url = API_URL + lang.file_path + '?format=TEXT'
    if not os.path.isdir(spell.dictionary_dir()):
        warn_msg = '{} does not exist, creating the directory'
        print(warn_msg.format(spell.dictionary_dir()))
        os.makedirs(spell.dictionary_dir())
    print('Downloading {}'.format(lang_url))
    dest = os.path.join(spell.dictionary_dir(), lang.file_path)
    download_dictionary(lang_url, dest)
    print('Done.')


def install(languages):
    """Install languages."""
    for lang in languages:
        try:
            install_lang(lang)
        except PermissionError as e:
            print(e)
            sys.exit(1)


def main():
    if configdata.DATA is None:
        configdata.init()
    parser = get_argparser()
    argv = sys.argv[1:]
    args = parser.parse_args(argv)
    languages = available_languages()
    if args.list:
        print_list(languages)
    elif not args.languages:
        parser.print_usage()
    else:
        try:
            install(filter_languages(languages, args.languages))
        except InvalidLanguageError as e:
            print(e)


if __name__ == '__main__':
    main()
