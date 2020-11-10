#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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
