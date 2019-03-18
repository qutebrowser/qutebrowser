#!/usr/bin/env python3
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

"""A script installing Hunspell dictionaries.

Use: python -m scripts.dictcli [-h] {list,update,remove-old,install} ...
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
from qutebrowser.utils import standarddir


API_URL = 'https://chromium.googlesource.com/chromium/deps/hunspell_dictionaries.git/+/master/'


class InvalidLanguageError(Exception):

    """Raised when requesting invalid languages."""

    def __init__(self, invalid_langs):
        msg = 'invalid languages: {}'.format(', '.join(invalid_langs))
        super().__init__(msg)


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
            self.local_filename = spell.local_filename(self.code)

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
        return spell.version(self.remote_path)

    @property
    def local_version(self):
        """Resolve the version of the local dictionary."""
        local_path = self.local_path
        if local_path is None:
            return None
        return spell.version(local_path)


def get_argparser():
    """Get the argparse parser."""
    desc = 'Install and manage Hunspell dictionaries for QtWebEngine.'
    parser = argparse.ArgumentParser(prog='dictcli',
                                     description=desc)
    subparsers = parser.add_subparsers(help='Command', dest='cmd')
    subparsers.required = True
    subparsers.add_parser('list',
                          help='Display the list of available languages.')
    subparsers.add_parser('update',
                          help='Update dictionaries')
    subparsers.add_parser('remove-old',
                          help='Remove old versions of dictionaries.')

    install_parser = subparsers.add_parser('install',
                                           help='Install dictionaries')
    install_parser.add_argument('language',
                                nargs='*',
                                help="A list of languages to install.")

    return parser


def version_str(version):
    return '.'.join(str(n) for n in version)


def print_list(languages):
    """Print the list of available languages."""
    pat = '{:<7}{:<26}{:<8}{:<5}'
    print(pat.format('Code', 'Name', 'Version', 'Installed'))
    for lang in languages:
        remote_version = version_str(lang.remote_version)
        local_version = '-'
        if lang.local_version is not None:
            local_version = version_str(lang.local_version)
            if lang.local_version < lang.remote_version:
                local_version += ' - update available!'
        print(pat.format(lang.code, lang.name, remote_version, local_version))


def valid_languages():
    """Return a mapping from valid language codes to their names."""
    option = configdata.DATA['spellcheck.languages']
    return option.typ.valtype.valid_values.descriptions


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


def language_list_from_api():
    """Return a JSON with a list of available languages from Google API."""
    listurl = API_URL + '?format=JSON'
    response = urllib.request.urlopen(listurl)
    # A special 5-byte prefix must be stripped from the response content
    # See: https://github.com/google/gitiles/issues/22
    #      https://github.com/google/gitiles/issues/82
    json_content = response.read()[5:]
    entries = json.loads(json_content.decode('utf-8'))['entries']
    parsed_entries = [parse_entry(entry) for entry in entries]
    return [entry for entry in parsed_entries if entry is not None]


def latest_yet(code2file, code, filename):
    """Determine whether the latest version so far."""
    if code not in code2file:
        return True
    return spell.version(code2file[code]) < spell.version(filename)


def available_languages():
    """Return a list of Language objects of all available languages."""
    lang_map = valid_languages()
    api_list = language_list_from_api()
    code2file = {}
    for code, filename in api_list:
        if latest_yet(code2file, code, filename):
            code2file[code] = filename
    return [
        Language(code, name, code2file[code])
        for code, name in lang_map.items()
        if code in code2file
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
    lang_url = API_URL + lang.remote_path + '?format=TEXT'
    if not os.path.isdir(spell.dictionary_dir()):
        msg = '{} does not exist, creating the directory'
        print(msg.format(spell.dictionary_dir()))
        os.makedirs(spell.dictionary_dir())
    print('Downloading {}'.format(lang_url))
    dest = os.path.join(spell.dictionary_dir(), lang.remote_path)
    download_dictionary(lang_url, dest)
    print('Done.')


def install(languages):
    """Install languages."""
    for lang in languages:
        try:
            print('Installing {}: {}'.format(lang.code, lang.name))
            install_lang(lang)
        except PermissionError as e:
            sys.exit(str(e))


def update(languages):
    """Update the given languages."""
    installed = [lang for lang in languages if lang.local_version is not None]
    for lang in installed:
        if lang.local_version < lang.remote_version:
            print('Upgrading {} from {} to {}'.format(
                lang.code,
                version_str(lang.local_version),
                version_str(lang.remote_version)))
            install_lang(lang)


def remove_old(languages):
    """Remove old versions of languages."""
    installed = [lang for lang in languages if lang.local_version is not None]
    for lang in installed:
        local_files = spell.local_files(lang.code)
        for old_file in local_files[1:]:
            os.remove(os.path.join(spell.dictionary_dir(), old_file))


def main():
    if configdata.DATA is None:
        configdata.init()
    standarddir.init(None)

    parser = get_argparser()
    argv = sys.argv[1:]
    args = parser.parse_args(argv)
    languages = available_languages()
    if args.cmd == 'list':
        print_list(languages)
    elif args.cmd == 'update':
        update(languages)
    elif args.cmd == 'remove-old':
        remove_old(languages)
    elif not args.language:
        sys.exit('You must provide a list of languages to install.')
    else:
        try:
            install(filter_languages(languages, args.language))
        except InvalidLanguageError as e:
            print(e)


if __name__ == '__main__':
    main()
