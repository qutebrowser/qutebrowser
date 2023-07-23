#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SPDX-FileCopyrightText: jnphilipp <me@jnphilipp.org>
# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Opens all links to feeds defined in the head of a site
#
# Ideal for use with tabs_are_windows. Set a hotkey to launch this script, then:
#   :bind gF spawn --userscript openfeeds
#
# Use the hotkey to open the feeds in new tab/window, press 'gF' to open
#

import os
import re

from bs4 import BeautifulSoup
from urllib.parse import urljoin

with open(os.environ['QUTE_HTML'], 'r') as f:
    soup = BeautifulSoup(f)
with open(os.environ['QUTE_FIFO'], 'w') as f:
    for link in soup.find_all('link', rel='alternate', type=re.compile(r'application/((rss|rdf|atom)\+)?xml|text/xml')):
        f.write('open -t %s\n' % urljoin(os.environ['QUTE_URL'], link.get('href')))
