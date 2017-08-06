#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et

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
import sys

from qutebrowser.browser.webengine import spell


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
        print('{1}\t{0}'.format(lang.name, lang.code))


def main():
    parser = get_argparser()
    argv = sys.argv[1:]
    args = parser.parse_args(argv)
    languages = spell.get_available_languages()
    if args.list:
        print_list(languages)
    elif not args.languages:
        parser.print_usage()
    else:
        try:
            spell.install(spell.filter_languages(languages, args.languages))
        except ValueError as e:
            print(e)


if __name__ == '__main__':
    main()
