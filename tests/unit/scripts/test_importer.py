#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import pathlib
import pytest
from scripts import importer

_samples = pathlib.Path('tests/unit/scripts/importer_sample')


def qm_expected(input_format):
    """Read expected quickmark-formatted output."""
    return (_samples / input_format / 'quickmarks').read_text(encoding='utf-8')


def bm_expected(input_format):
    """Read expected bookmark-formatted output."""
    return (_samples / input_format / 'bookmarks').read_text(encoding='utf-8')


def search_expected(input_format):
    """Read expected search-formatted (config.py) output."""
    return (_samples / input_format / 'config_py').read_text(encoding='utf-8')


def sample_input(input_format):
    """Get the sample input path."""
    return str(_samples / input_format / 'input')


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
    importer.import_chrome(sample_input('chrome'), ['bookmark'], 'bookmark')
    imported = capsys.readouterr()[0]
    assert imported == bm_expected('chrome')


def test_chrome_quickmarks(capsys):
    """Read sample bookmarks from chrome profile."""
    importer.import_chrome(sample_input('chrome'), ['bookmark'], 'quickmark')
    imported = capsys.readouterr()[0]
    assert imported == qm_expected('chrome')


def test_chrome_searches(capsys):
    """Read sample searches from chrome profile."""
    importer.import_chrome(sample_input('chrome'), ['search'], 'search')
    imported = capsys.readouterr()[0]
    assert imported == search_expected('chrome')


def test_html_bookmarks(capsys):
    importer.import_html_bookmarks(
        sample_input('html'), ['bookmark', 'keyword'], 'bookmark')
    imported = capsys.readouterr()[0]
    assert imported == bm_expected('html')


def test_html_quickmarks(capsys):
    importer.import_html_bookmarks(
        sample_input('html'), ['bookmark', 'keyword'], 'quickmark')
    imported = capsys.readouterr()[0]
    assert imported == qm_expected('html')


def test_html_searches(capsys):
    importer.import_html_bookmarks(
        sample_input('html'), ['search'], 'search')
    imported = capsys.readouterr()[0]
    assert imported == search_expected('html')


def test_mozilla_bookmarks(capsys):
    importer.import_moz_places(
        sample_input('mozilla'), ['bookmark', 'keyword'], 'bookmark')
    imported = capsys.readouterr()[0]
    assert imported == bm_expected('mozilla')


def test_mozilla_quickmarks(capsys):
    importer.import_moz_places(
        sample_input('mozilla'), ['bookmark', 'keyword'], 'quickmark')
    imported = capsys.readouterr()[0]
    assert imported == qm_expected('mozilla')


def test_mozilla_searches(capsys):
    importer.import_moz_places(sample_input('mozilla'), ['search'], 'search')
    imported = capsys.readouterr()[0]
    assert imported == search_expected('mozilla')
