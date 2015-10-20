#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

"""Fetch list of popular user-agents.

The script is based on a gist posted by github.com/averrin, the ouput of this
script is formatted to be pasted into configtypes.py.
"""

import requests
from lxml import html

url = 'https://techblog.willshouse.com/2012/01/03/most-common-user-agents/'
page = requests.get(url)
page = html.fromstring(page.text)
path = '//*[@id="post-2229"]/div[2]/table/tbody'
table = page.xpath(path)[0]

indent = "    "
print("%sdef complete(self):" % indent)
print("%s\"\"\"Complete a list of common user agents.\"\"\"" % (2 * indent))
print("%sout = [" % (2 * indent))
for row in table[:12]:
    ua = row[1].text_content()
    browser = row[2].text_content()
    print("%s(\'%s\',\n%s \"%s\")," % (3 * indent, ua, 3 * indent, browser))
print("%s]\n%sreturn out\n" % (2 * indent, 2 * indent))
