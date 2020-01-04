#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2014-2018 Claude (longneck) <longneck@scratchbook.ch>

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


"""Tool to import data from other browsers.

Currently importing bookmarks from Netscape Bookmark files and Mozilla
profiles is supported.
"""


import argparse
import sqlite3
import os
import urllib.parse
import json
import string

browser_default_input_format = {
    'chromium': 'chrome',
    'chrome': 'chrome',
    'ie': 'netscape',
    'firefox': 'mozilla',
    'seamonkey': 'mozilla',
    'palemoon': 'mozilla',
}


def main():
    args = get_args()
    bookmark_types = []
    output_format = None
    input_format = args.input_format
    if args.search_output:
        bookmark_types = ['search']
        if args.oldconfig:
            output_format = 'oldsearch'
        else:
            output_format = 'search'
    else:
        if args.bookmark_output:
            output_format = 'bookmark'
        elif args.quickmark_output:
            output_format = 'quickmark'
        if args.import_bookmarks:
            bookmark_types.append('bookmark')
        if args.import_keywords:
            bookmark_types.append('keyword')
    if not bookmark_types:
        bookmark_types = ['bookmark', 'keyword']
    if not output_format:
        output_format = 'quickmark'
    if not input_format:
        if args.browser:
            input_format = browser_default_input_format[args.browser]
        else:
            #default to netscape
            input_format = 'netscape'

    import_function = {
        'netscape': import_netscape_bookmarks,
        'mozilla': import_moz_places,
        'chrome': import_chrome,
    }
    import_function[input_format](args.bookmarks, bookmark_types,
                                  output_format)


def get_args():
    """Get the argparse parser."""
    parser = argparse.ArgumentParser(
        epilog="To import bookmarks from Chromium, Firefox or IE, "
        "export them to HTML in your browsers bookmark manager. ")
    parser.add_argument(
        'browser',
        help="Which browser? {%(choices)s}",
        choices=browser_default_input_format.keys(),
        nargs='?',
        metavar='browser')
    parser.add_argument(
        '-i',
        '--input-format',
        help='Which input format? (overrides browser default; "netscape" if '
        'neither given)',
        choices=set(browser_default_input_format.values()),
        required=False)
    parser.add_argument(
        '-b',
        '--bookmark-output',
        help="Output in bookmark format.",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        '-q',
        '--quickmark-output',
        help="Output in quickmark format (default).",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        '-s',
        '--search-output',
        help="Output config.py search engine format (negates -B and -K)",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        '--oldconfig',
        help="Output search engine format for old qutebrowser.conf format",
        default=False,
        action='store_true',
        required=False)
    parser.add_argument(
        '-B',
        '--import-bookmarks',
        help="Import plain bookmarks (can be combiend with -K)",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        '-K',
        '--import-keywords',
        help="Import keywords (can be combined with -B)",
        action='store_true',
        default=False,
        required=False)
    parser.add_argument(
        'bookmarks',
        help="Bookmarks file (html format) or "
        "profile folder (Mozilla format)")
    args = parser.parse_args()
    return args


def search_escape(url):
    """Escape URLs such that preexisting { and } are handled properly.

    Will obviously trash a properly-formatted qutebrowser URL.
    """
    return url.replace('{', '{{').replace('}', '}}')


def opensearch_convert(url):
    """Convert a basic OpenSearch URL into something qutebrowser can use.

    Exceptions:
        KeyError:
            An unknown and required parameter is present in the URL. This
            usually means there's browser/addon specific functionality needed
            to build the URL (I'm looking at you and your browser, Google) that
            obviously won't be present here.
    """
    subst = {
        'searchTerms': '%s',  # for proper escaping later
        'language': '*',
        'inputEncoding': 'UTF-8',
        'outputEncoding': 'UTF-8'
    }

    # remove optional parameters (even those we don't support)
    for param in string.Formatter().parse(url):
        if param[1]:
            if param[1].endswith('?'):
                url = url.replace('{' + param[1] + '}', '')
            elif param[2] and param[2].endswith('?'):
                url = url.replace('{' + param[1] + ':' + param[2] + '}', '')
    return search_escape(url.format(**subst)).replace('%s', '{}')


def import_netscape_bookmarks(bookmarks_file, bookmark_types, output_format):
    """Import bookmarks from a NETSCAPE-Bookmark-file v1.

    Generated by Chromium, Firefox, IE and possibly more browsers. Not all
    export all possible bookmark types:
        - Firefox mostly works with everything
        - Chrome doesn't support keywords at all; searches are a separate
          database
    """
    import bs4
    with open(bookmarks_file, encoding='utf-8') as f:
        soup = bs4.BeautifulSoup(f, 'html.parser')
    bookmark_query = {
        'search': lambda tag: (
            (tag.name == 'a') and
            ('shortcuturl' in tag.attrs) and
            ('%s' in tag['href'])),
        'keyword': lambda tag: (
            (tag.name == 'a') and
            ('shortcuturl' in tag.attrs) and
            ('%s' not in tag['href'])),
        'bookmark': lambda tag: (
            (tag.name == 'a') and
            ('shortcuturl' not in tag.attrs) and
            (tag.string)),
    }
    output_template = {
        'search': {
            'search':
            "c.url.searchengines['{tag[shortcuturl]}'] = "
            "'{tag[href]}' #{tag.string}"
        },
        'oldsearch': {
            'search': '{tag[shortcuturl]} = {tag[href]} #{tag.string}',
        },
        'bookmark': {
            'bookmark': '{tag[href]} {tag.string}',
            'keyword': '{tag[href]} {tag.string}'
        },
        'quickmark': {
            'bookmark': '{tag.string} {tag[href]}',
            'keyword': '{tag[shortcuturl]} {tag[href]}'
        }
    }
    bookmarks = []
    for typ in bookmark_types:
        tags = soup.findAll(bookmark_query[typ])
        for tag in tags:
            if typ == 'search':
                tag['href'] = search_escape(tag['href']).replace('%s', '{}')
            if tag['href'] not in bookmarks:
                bookmarks.append(
                    output_template[output_format][typ].format(tag=tag))
    for bookmark in bookmarks:
        print(bookmark)


def import_moz_places(profile, bookmark_types, output_format):
    """Import bookmarks from a Mozilla profile's places.sqlite database."""
    place_query = {
        'bookmark': (
            "SELECT DISTINCT moz_bookmarks.title,moz_places.url "
            "FROM moz_bookmarks,moz_places "
            "WHERE moz_places.id=moz_bookmarks.fk "
            "AND moz_places.id NOT IN (SELECT place_id FROM moz_keywords) "
            "AND moz_places.url NOT LIKE 'place:%';"
        ),  # Bookmarks with no keywords assigned
        'keyword': (
            "SELECT moz_keywords.keyword,moz_places.url "
            "FROM moz_keywords,moz_places,moz_bookmarks "
            "WHERE moz_places.id=moz_bookmarks.fk "
            "AND moz_places.id=moz_keywords.place_id "
            "AND moz_places.url NOT LIKE '%!%s%' ESCAPE '!';"
        ),  # Bookmarks with keywords assigned but no %s substitution
        'search': (
            "SELECT moz_keywords.keyword, "
            "    moz_bookmarks.title, "
            "    search_conv(moz_places.url) AS url "
            "FROM moz_keywords,moz_places,moz_bookmarks "
            "WHERE moz_places.id=moz_bookmarks.fk "
            "AND moz_places.id=moz_keywords.place_id "
            "AND moz_places.url LIKE '%!%s%' ESCAPE '!';"
        )  # bookmarks with keyword and %s substitution
    }
    out_template = {
        'bookmark': {
            'bookmark': '{url} {title}',
            'keyword': '{url} {keyword}'
        },
        'quickmark': {
            'bookmark': '{title} {url}',
            'keyword': '{keyword} {url}'
        },
        'oldsearch': {
            'search': '{keyword} {url} #{title}'
        },
        'search': {
            'search': "c.url.searchengines['{keyword}'] = '{url}' #{title}"
        }
    }

    def search_conv(url):
        return search_escape(url).replace('%s', '{}')

    places = sqlite3.connect(os.path.join(profile, "places.sqlite"))
    places.create_function('search_conv', 1, search_conv)
    places.row_factory = sqlite3.Row
    c = places.cursor()
    for typ in bookmark_types:
        c.execute(place_query[typ])
        for row in c:
            print(out_template[output_format][typ].format(**row))


def import_chrome(profile, bookmark_types, output_format):
    """Import bookmarks and search keywords from Chrome-type profiles.

    On Chrome, keywords and search engines are the same thing and handled in
    their own database table; bookmarks cannot have associated keywords. This
    is why the dictionary lookups here are much simpler.
    """
    out_template = {
        'bookmark': '{url} {name}',
        'quickmark': '{name} {url}',
        'search': "c.url.searchengines['{keyword}'] = '{url}'",
        'oldsearch': '{keyword} {url}'
    }

    if 'search' in bookmark_types:
        webdata = sqlite3.connect(os.path.join(profile, 'Web Data'))
        c = webdata.cursor()
        c.execute('SELECT keyword,url FROM keywords;')
        for keyword, url in c:
            try:
                url = opensearch_convert(url)
                print(out_template[output_format].format(
                    keyword=keyword, url=url))
            except KeyError:
                print('# Unsupported parameter in url for {}; skipping....'.
                      format(keyword))

    else:
        with open(os.path.join(profile, 'Bookmarks'), encoding='utf-8') as f:
            bookmarks = json.load(f)

        def bm_tree_walk(bm, template):
            """Recursive function to walk through bookmarks."""
            if not isinstance(bm, dict):
                return
            assert 'type' in bm, bm
            if bm['type'] == 'url':
                if urllib.parse.urlparse(bm['url']).scheme != 'chrome':
                    print(template.format(**bm))
            elif bm['type'] == 'folder':
                for child in bm['children']:
                    bm_tree_walk(child, template)

        for root in bookmarks['roots'].values():
            bm_tree_walk(root, out_template[output_format])


if __name__ == '__main__':
    main()
