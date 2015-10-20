#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 lamarpavel
# Copyright 2015 Alexey Nabrodov (Averrin)
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

The script is based on a gist posted by github.com/averrin, the ouput of this
script is formatted to be pasted into configtypes.py.
"""

import requests
from lxml import html   # pylint: disable=import-error

# Fetch list of popular user-agents and store the relevant strings
url = 'https://techblog.willshouse.com/2012/01/03/most-common-user-agents/'
page = requests.get(url)
page = html.fromstring(page.text)
path = '//*[@id="post-2229"]/div[2]/table/tbody'
table = page.xpath(path)[0]
indent = "    "

# Print function defition followed by an automatically fetched list of popular
# user agents and a few additional entries for diversity.
print("%sdef complete(self):" % indent)
print("%s\"\"\"Complete a list of common user agents.\"\"\"" % (2 * indent))
print("%sout = [" % (2 * indent))
for row in table[:12]:
    ua = row[1].text_content()
    browser = row[2].text_content()
    print("%s(\'%s\',\n%s \"%s\")," % (3 * indent, ua, 3 * indent, browser))
print("""
            ('Mozilla/5.0 (iPhone; CPU iPhone OS 8_1_2 like Mac OS X) '
             'AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 '
             'Mobile/12B440 Safari/600.1.4',
             "Mobile Safari 8.0 iOS"),
            ('Mozilla/5.0 (Android; Mobile; rv:35.0) Gecko/35.0 Firefox/35.0',
             "Firefox 35, Android"),
            ('Mozilla/5.0 (Linux; Android 5.0.2; One Build/KTU84L.H4) '
             'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 '
             'Chrome/37.0.0.0 Mobile Safari/537.36',
             "Android Browser")
""")
print("%s]\n%sreturn out\n" % (2 * indent, 2 * indent))
