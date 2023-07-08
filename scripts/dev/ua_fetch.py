#!/usr/bin/env python3
# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Fetch and print the most common user agents.

This script fetches the most common user agents according to
https://github.com/Kikobeats/top-user-agents, and prints the most recent
Chrome user agent for Windows, macOS and Linux.
"""

import math
import sys
import textwrap

import requests
import qutebrowser.config.websettings


def version(ua):
    """Comparable version of a user agent."""
    return tuple(int(v) for v in ua.upstream_browser_version.split('.')[:2])


def wrap(ini, sub, string):
    return textwrap.wrap(string, width=80, initial_indent=ini, subsequent_indent=sub)


# pylint: disable-next=missing-timeout
response = requests.get('https://raw.githubusercontent.com/Kikobeats/top-user-agents/master/index.json')

if response.status_code != 200:
    print('Unable to fetch the user agent index', file=sys.stderr)
    sys.exit(1)

ua_checks = {
    'Win10': lambda ua: ua.os_info.startswith('Windows NT'),
    'macOS': lambda ua: ua.os_info.startswith('Macintosh'),
    'Linux': lambda ua: ua.os_info.startswith('X11'),
}

ua_strings = {}
ua_versions = {}
ua_names = {}

for ua_string in reversed(response.json()):
    # reversed to prefer more common versions

    # Filter out browsers that are not Chrome-based
    parts = ua_string.split()
    if not any(part.startswith("Chrome/") for part in parts):
        continue
    if any(part.startswith("OPR/") or part.startswith("Edg/") for part in parts):
        continue
    if 'Chrome/99.0.7113.93' in parts:
        # Fake or false-positive entry
        continue

    user_agent = qutebrowser.config.websettings.UserAgent.parse(ua_string)

    # check which os_string conditions are met and select the most recent version
    for key, check in ua_checks.items():
        if check(user_agent):
            v = version(user_agent)
            if v >= ua_versions.get(key, (-math.inf,)):
                ua_versions[key] = v
                ua_strings[key] = ua_string
                ua_names[key] = f'Chrome {v[0]} {key}'

for key, ua_string in ua_strings.items():
    quoted_ua_string = f'"{ua_string}"'
    for line in wrap("      - - ", "          ", quoted_ua_string):
        print(line)
    for line in wrap("        - ", "          ", ua_names[key]):
        print(line)
