# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""A Chromium-like URL matching pattern.

See:
https://developer.chrome.com/apps/match_patterns
https://cs.chromium.org/chromium/src/extensions/common/url_pattern.cc
https://cs.chromium.org/chromium/src/extensions/common/url_pattern.h
"""

import contextlib
import urllib.parse

from qutebrowser.utils import utils


class UrlPattern:

    """A Chromium-like URL matching pattern."""

    SCHEMES = ['https', 'http', 'ftp', 'file', 'chrome', 'qute', 'about']

    def __init__(self, pattern):
        # Make sure all attributes are initialized if we exit early.
        self._pattern = pattern
        self._match_all = False
        self._match_subdomains = False
        self._scheme = None
        self._host = None
        self._path = None
        self._port = None

        # > The special pattern <all_urls> matches any URL that starts with a
        # > permitted scheme.
        if pattern == '<all_urls>':
            self._match_all = True
            return

        if '\0' in pattern:
            raise ValueError("May not contain NUL byte")

        # > If the scheme is *, then it matches either http or https, and not
        # > file, or ftp.
        # Note we deviate from that, as per-URL settings aren't security
        # relevant.
        if pattern.startswith('*:'):  # Any scheme
            self._scheme = '*'
            pattern = 'any:' + pattern[2:]  # Make it parseable again

        # We use urllib.parse instead of QUrl here because it can handle
        # hosts with * in them.
        parsed = urllib.parse.urlparse(pattern)
        # "Changed in version 3.6: Out-of-range port numbers now raise
        # ValueError, instead of returning None."
        if parsed is None:
            raise ValueError("Failed to parse {}".format(pattern))

        self._init_scheme(parsed)
        self._init_host(parsed)
        self._init_path(parsed)
        self._init_port(parsed)

    def _init_scheme(self, parsed):
        if not parsed.scheme:
            raise ValueError("No scheme given")
        if parsed.scheme not in self.SCHEMES:
            raise ValueError("Unknown scheme {}".format(parsed.scheme))
        self._scheme = parsed.scheme

    def _init_path(self, parsed):
        if self._scheme == 'about' and not parsed.path.strip():
            raise ValueError("Pattern without path")
        self._path = parsed.path

    def _init_host(self, parsed):
        if self._scheme != 'about' and not parsed.netloc.strip():
            raise ValueError("Pattern without host")
        host_parts = parsed.netloc.split('.')
        if host_parts[0] == '*':
            host_parts = host_parts[1:]
            self._match_subdomains = True
        self._host = '.'.join(host_parts)
        if '*' in self._host:
            # Only * or *.foo is allowed as host.
            raise ValueError("Invalid host wildcard")

    def _init_port(self, parsed):
        # FIXME validation?
        self._port = parsed.port

    def __repr__(self):
        return utils.get_repr(self, pattern=self._pattern, constructor=True)
