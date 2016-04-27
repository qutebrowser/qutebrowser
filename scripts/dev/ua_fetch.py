#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 lamarpavel
# Copyright 2015-2016 Alexey Nabrodov (Averrin)
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


"""Fetch list of popular user-agents.

The script is based on a gist posted by github.com/averrin, the output of this
script is formatted to be pasted into configtypes.py.
"""

import requests
from lxml import html  # pylint: disable=import-error


def fetch():
    """Fetch list of popular user-agents.

    Return:
        List of relevant strings.
    """
    url = 'https://techblog.willshouse.com/2012/01/03/most-common-user-agents/'
    page = requests.get(url)
    page = html.fromstring(page.text)
    path = '//*[@id="post-2229"]/div[2]/table/tbody'
    return page.xpath(path)[0]


def filter_list(complete_list, browsers):
    """Filter the received list based on a look up table.

    The LUT should be a dictionary of the format {browser: versions}, where
    'browser' is the name of the browser (eg. "Firefox") as string and
    'versions' is a set of different versions of this browser that should be
    included when found (eg. {"Linux", "MacOSX"}). This function returns a
    dictionary with the same keys as the LUT, but storing lists of tuples
    (user_agent, browser_description) as values.
    """
    # pylint: disable=too-many-nested-blocks
    table = {}
    for entry in complete_list:
        # Tuple of (user_agent, browser_description)
        candidate = (entry[1].text_content(), entry[2].text_content())
        for name in browsers:
            found = False
            if name.lower() in candidate[1].lower():
                for version in browsers[name]:
                    if version.lower() in candidate[1].lower():
                        if table.get(name) is None:
                            table[name] = []
                        table[name].append(candidate)
                        browsers[name].remove(version)
                        found = True
                        break
            if found:
                break
    return table


def add_diversity(table):
    """Insert a few additional entries for diversity into the dict.

    (as returned by filter_list())
    """
    table["Obscure"] = [
        ('Mozilla/5.0 (compatible; Googlebot/2.1; '
         '+http://www.google.com/bot.html',
         "Google Bot"),
        ('Wget/1.16.1 (linux-gnu)',
         "wget 1.16.1"),
        ('curl/7.40.0',
         "curl 7.40.0")
    ]
    return table


def main():
    """Generate user agent code."""
    fetched = fetch()
    lut = {
        "Firefox": {"Win", "MacOSX", "Linux", "Android"},
        "Chrome": {"Win", "MacOSX", "Linux"},
        "Safari": {"MacOSX", "iOS"}
    }
    filtered = filter_list(fetched, lut)
    filtered = add_diversity(filtered)

    tab = "    "
    print(tab + "def complete(self):")
    print((2 * tab) + "\"\"\"Complete a list of common user agents.\"\"\"")
    print((2 * tab) + "%sout = [")

    for browser in ["Firefox", "Safari", "Chrome", "Obscure"]:
        for it in filtered[browser]:
            print("{}(\'{}\',\n{} \"{}\"),".format(3 * tab, it[0],
                                                   3 * tab, it[1]))
        print("")

    print("""\
            ('Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like '
             'Gecko',
             "IE 11.0 for Desktop  Win7 64-bit")""")

    print("{}]\n{}return out\n".format(2 * tab, 2 * tab))


if __name__ == '__main__':
    main()
