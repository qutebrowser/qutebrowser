#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import pytest
from scripts import importer

_chrome_profile = 'tests/unit/scripts/chrome-profile'


def test_opensearch_convert():
    urls = [
        # simple search query
        ('http://foo.bar/s?q={searchTerms}', 'http://foo.bar/s?q={}'),
        # simple search query with supported additional parameter
        ('http://foo.bar/s?q={searchTerms}&enc={inputEncoding}',
         'http://foo.bar/s?q={}&enc=UTF-8'),
        # same as above but with supported optional parameter
        ('http://foo.bar/s?q={searchTerms}&enc={inputEncoding?}',
         'http://foo.bar/s?q={}&enc='),
        # unsupported-but-optional parameter
        ('http://foo.bar/s?q={searchTerms}&opt={unsupported?}',
         'http://foo.bar/s?q={}&opt='),
        # unsupported-but-optional subset parameter
        ('http://foo.bar/s?q={searchTerms}&opt={unsupported:unsupported?}',
         'http://foo.bar/s?q={}&opt=')
    ]
    for os_url, qb_url in urls:
        assert importer.opensearch_convert(os_url) == qb_url


def test_opensearch_convert_unsupported():
    """pass an unsupported, required parameter."""
    with pytest.raises(KeyError):
        os_url = 'http://foo.bar/s?q={searchTerms}&req={unsupported}'
        importer.opensearch_convert(os_url)


def test_chrome_bookmarks(capsys):
    """Read sample bookmarks from chrome profile."""
    expected = ('Foo http://foo.com/\n' 'Bar http://bar.com/\n')
    importer.import_chrome(_chrome_profile, ['bookmark'], 'quickmark')
    imported = capsys.readouterr()[0]
    assert imported == expected


def test_chrome_searches(capsys):
    """Read sample searches from chrome profile."""
    expected = (
        "# Unsupported parameter in url for google.com; skipping....\n"
        "c.url.searchengines['bing.com'] = 'https://www.bing.com/search?q={}&PC=U316&FORM=CHROMN'\n"
        "c.url.searchengines['yahoo.com'] = 'https://search.yahoo.com/search?ei=UTF-8&fr=crmas&p={}'\n"
        "c.url.searchengines['aol.com'] = 'https://search.aol.com/aol/search?q={}'\n"
        "c.url.searchengines['ask.com'] = 'http://www.ask.com/web?q={}'\n")
    importer.import_chrome(_chrome_profile, ['search'], 'search')
    imported = capsys.readouterr()[0]
    assert imported == expected
