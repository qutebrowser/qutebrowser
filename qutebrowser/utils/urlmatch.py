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

import ipaddress
import fnmatch
import contextlib
import urllib.parse

from qutebrowser.utils import utils


class ParseError(Exception):

    """Raised when a pattern could not be parsed."""


class UrlPattern:

    """A Chromium-like URL matching pattern.

    Attributes:
        _pattern: The given pattern as string.
        _match_all: Whether the pattern should match all URLs.
        _match_subdomains: Whether the pattern should match subdomains of the
                           given host.
        _scheme: The scheme to match to, or None to match any scheme.
                 Note that with Chromium, '*'/None only matches http/https and
                 not file/ftp. We deviate from that as per-URL settings aren't
                 security relevant.
        _host: The host to match to, or None for any host.
        _path: The path to match to, or None for any path.
        _port: The port to match to as integer, or None for any port.
    """

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
            raise ParseError("May not contain NUL byte")

        pattern = self._fixup_pattern(pattern)

        # We use urllib.parse instead of QUrl here because it can handle
        # hosts with * in them.
        try:
            parsed = urllib.parse.urlparse(pattern)
        except ValueError as e:
            raise ParseError(str(e))
        # "Changed in version 3.6: Out-of-range port numbers now raise
        # ValueError, instead of returning None."
        if parsed is None:
            raise ParseError("Failed to parse {}".format(pattern))

        self._init_scheme(parsed)
        self._init_host(parsed)
        self._init_path(parsed)
        self._init_port(parsed)

    def _fixup_pattern(self, pattern):
        """Make sure the given pattern is parseable by urllib.parse."""
        if pattern.startswith('*:'):  # Any scheme, but *:// is unparseable
            pattern = 'any:' + pattern[2:]

        # Chromium handles file://foo like file:///foo
        if (pattern.startswith('file://') and
                not pattern.startswith('file:///')):
            pattern = 'file:///' + pattern[len("file://"):]

        return pattern

    def _init_scheme(self, parsed):
        if not parsed.scheme:
            raise ParseError("No scheme given")
        elif parsed.scheme == 'any':
            self._scheme = None
            return

        self._scheme = parsed.scheme

    def _init_path(self, parsed):
        if self._scheme == 'about' and not parsed.path.strip():
            raise ParseError("Pattern without path")

        self._path = None if parsed.path == '/*' else parsed.path

    def _init_host(self, parsed):
        """Parse the host from the given URL.

        Deviation from Chromium:
        - http://:1234/ is not a valid URL because it has no host.
        """
        if parsed.hostname is None or not parsed.hostname.strip():
            if self._scheme not in ['about', 'file', 'data', 'javascript']:
                raise ParseError("Pattern without host")
            assert self._host is None
            return

        # FIXME what about multiple dots?
        host_parts = parsed.hostname.rstrip('.').split('.')
        if host_parts[0] == '*':
            host_parts = host_parts[1:]
            self._match_subdomains = True

        if not host_parts:
            self._host = None
            return

        self._host = '.'.join(host_parts)

        if self._host.endswith('.*'):
            # Special case to have a nicer error
            raise ParseError("TLD wildcards are not implemented yet")
        elif '*' in self._host:
            # Only * or *.foo is allowed as host.
            raise ParseError("Invalid host wildcard")

    def _init_port(self, parsed):
        """Parse the port from the given URL.

        Deviation from Chromium:
        - We use None instead of "*" if there's no port filter.
        """
        if parsed.netloc.endswith(':*'):
            # We can't access parsed.port as it tries to run int()
            self._port = None
        elif parsed.netloc.endswith(':'):
            raise ParseError("Empty port")
        else:
            try:
                self._port = parsed.port
            except ValueError:
                raise ParseError("Invalid port")

        allows_ports = {'https': True, 'http': True, 'ftp': True,
                        'file': False, 'chrome': False, 'qute': False,
                        'about': False, 'data': False, 'javascript': False,
                        None: True}
        if not allows_ports[self._scheme] and self._port is not None:
            raise ParseError("Ports are unsupported with {} scheme".format(
                self._scheme))

    def __repr__(self):
        return utils.get_repr(self, pattern=self._pattern, constructor=True)

    def _matches_scheme(self, scheme):
        return self._scheme is None or self._scheme == scheme

    def _matches_host(self, host):
        # FIXME what about multiple dots?
        host = host.rstrip('.')

        if self._host is None:
            return True

        # If the hosts are exactly equal, we have a match.
        if host == self._host:
            return True

        # If we're matching subdomains, and we have no host in the match pattern,
        # that means that we're matching all hosts, which means we have a match no
        # matter what the test host is.
        if self._match_subdomains and not self._host:
            return True

        # Otherwise, we can only match if our match pattern matches subdomains.
        if not self._match_subdomains:
            return False

        # We don't do subdomain matching against IP addresses, so we can give up now
        # if the test host is an IP address.
        if not utils.raises(ValueError, ipaddress.ip_address, host):
            return False

        # Check if the test host is a subdomain of our host.
        if len(host) <= (len(self._host) + 1):
            return False

        if not host.endswith(self._host):
            return False

        return host[len(host) - len(self._host) - 1] == '.'

    def _matches_port(self, port):
        return self._port is None or self._port == port

    def _matches_path(self, path):
        if self._path is None:
            return True

        # Match 'google.com' with 'google.com/'
        # FIXME use the no-copy approach Chromium has in URLPattern::MatchesPath
        # for performance?
        if path + '/*' == self._path:
            return True

        # FIXME Chromium seems to have a more optimized glob matching which
        # doesn't rely on regexes. Do we need that too?
        return fnmatch.fnmatchcase(path, self._path)

    def matches(self, qurl):
        """Check if the pattern matches the given QUrl."""
        # FIXME do we need to check this early?
        if not self._matches_scheme(qurl.scheme()):
            return False

        if self._match_all:
            return True

        # FIXME ignore for file:// like Chromium?
        if not self._matches_host(qurl.host()):
            return False
        if not self._matches_port(qurl.port()):
            return False
        if not self._matches_path(qurl.path()):
            return False

        return True
