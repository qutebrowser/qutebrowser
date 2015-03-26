#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Print the unittest coverage based on the HTML output.

This can probably be deleted when switching to py.test
"""


import os.path
import html.parser


class Parser(html.parser.HTMLParser):

    """HTML parser to get the percentage from coverage's HTML output."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._active = False
        self.percentage = None

    def handle_starttag(self, tag, attrs):
        if tag == 'span' and dict(attrs).get('class', None) == 'pc_cov':
            self._active = True

    def handle_endtag(self, _tag):
        self._active = False

    def handle_data(self, data):
        if self._active:
            self.percentage = data


def main():
    """Main entry point."""
    p = Parser()
    with open(os.path.join('htmlcov', 'index.html'), encoding='utf-8') as f:
        p.feed(f.read())
    print('COVERAGE: {}'.format(p.percentage))


if __name__ == '__main__':
    main()
