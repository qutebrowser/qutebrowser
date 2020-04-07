# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import typing
import urllib.parse

from PyQt5.QtCore import QUrl

from qutebrowser.utils import utils, qtutils


class ParseError(Exception):

    """Raised when a pattern could not be parsed."""


class UrlPattern:

    """A Chromium-like URL matching pattern.

    Class attributes:
        _DEFAULT_PORTS: The default ports used for schemes which support ports.
        _SCHEMES_WITHOUT_HOST: Schemes which don't need a host.

    Attributes:
        host: The host to match to, or None for any host.
        _pattern: The given pattern as string.
        _match_all: Whether the pattern should match all URLs.
        _match_subdomains: Whether the pattern should match subdomains of the
                           given host.
        _scheme: The scheme to match to, or None to match any scheme.
                 Note that with Chromium, '*'/None only matches http/https and
                 not file/ftp. We deviate from that as per-URL settings aren't
                 security relevant.
        _path: The path to match to, or None for any path.
        _port: The port to match to as integer, or None for any port.
    """

    _DEFAULT_PORTS = {'https': 443, 'http': 80, 'ftp': 21}
    _SCHEMES_WITHOUT_HOST = ['about', 'file', 'data', 'javascript']

    def __init__(self, pattern: str) -> None:
        # Make sure all attributes are initialized if we exit early.
        self._pattern = pattern
        self._match_all = False
        self._match_subdomains = False  # type: bool
        self._scheme = None  # type: typing.Optional[str]
        self.host = None  # type: typing.Optional[str]
        self._path = None  # type: typing.Optional[str]
        self._port = None  # type: typing.Optional[int]

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

        assert parsed is not None

        self._init_scheme(parsed)
        self._init_host(parsed)
        self._init_path(parsed)
        self._init_port(parsed)

    def _to_tuple(self) -> typing.Tuple:
        """Get a pattern with information used for __eq__/__hash__."""
        return (self._match_all, self._match_subdomains, self._scheme,
                self.host, self._path, self._port)

    def __hash__(self) -> int:
        return hash(self._to_tuple())

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, UrlPattern):
            return NotImplemented
        return self._to_tuple() == other._to_tuple()

    def __repr__(self) -> str:
        return utils.get_repr(self, pattern=self._pattern, constructor=True)

    def __str__(self) -> str:
        return self._pattern

    def _fixup_pattern(self, pattern: str) -> str:
        """Make sure the given pattern is parseable by urllib.parse."""
        if pattern.startswith('*:'):  # Any scheme, but *:// is unparseable
            pattern = 'any:' + pattern[2:]

        schemes = tuple(s + ':' for s in self._SCHEMES_WITHOUT_HOST)
        if '://' not in pattern and not pattern.startswith(schemes):
            pattern = 'any://' + pattern

        # Chromium handles file://foo like file:///foo
        # FIXME This doesn't actually strip the hostname correctly.
        if (pattern.startswith('file://') and
                not pattern.startswith('file:///')):
            pattern = 'file:///' + pattern[len("file://"):]

        return pattern

    def _init_scheme(self, parsed: urllib.parse.ParseResult) -> None:
        """Parse the scheme from the given URL.

        Deviation from Chromium:
        - We assume * when no scheme has been given.
        """
        if not parsed.scheme:
            raise ParseError("Missing scheme")

        if parsed.scheme == 'any':
            self._scheme = None
            return

        self._scheme = parsed.scheme

    def _init_path(self, parsed: urllib.parse.ParseResult) -> None:
        """Parse the path from the given URL.

        Deviation from Chromium:
        - We assume * when no path has been given.
        """
        if self._scheme == 'about' and not parsed.path.strip():
            raise ParseError("Pattern without path")

        if parsed.path == '/*':
            self._path = None
        elif not parsed.path:
            # When the user doesn't add a trailing slash, we assume the pattern
            # matches any path.
            self._path = None
        else:
            self._path = parsed.path

    def _init_host(self, parsed: urllib.parse.ParseResult) -> None:
        """Parse the host from the given URL.

        Deviation from Chromium:
        - http://:1234/ is not a valid URL because it has no host.
        """
        if parsed.hostname is None or not parsed.hostname.strip():
            if self._scheme not in self._SCHEMES_WITHOUT_HOST:
                raise ParseError("Pattern without host")
            assert self.host is None
            return

        if parsed.netloc.startswith('['):
            # Using QUrl parsing to minimize ipv6 addresses
            url = QUrl()
            url.setHost(parsed.hostname)
            if not url.isValid():
                raise ParseError(url.errorString())
            self.host = url.host()
            return

        # FIXME what about multiple dots?
        host_parts = parsed.hostname.rstrip('.').split('.')
        if host_parts[0] == '*':
            host_parts = host_parts[1:]
            self._match_subdomains = True

        if not host_parts:
            self.host = None
            return

        self.host = '.'.join(host_parts)

        if self.host.endswith('.*'):
            # Special case to have a nicer error
            raise ParseError("TLD wildcards are not implemented yet")
        if '*' in self.host:
            # Only * or *.foo is allowed as host.
            raise ParseError("Invalid host wildcard")

    def _init_port(self, parsed: urllib.parse.ParseResult) -> None:
        """Parse the port from the given URL.

        Deviation from Chromium:
        - We use None instead of "*" if there's no port filter.
        """
        if parsed.netloc.endswith(':*'):
            # We can't access parsed.port as it tries to run int()
            self._port = None
        elif parsed.netloc.endswith(':'):
            raise ParseError("Invalid port: Port is empty")
        else:
            try:
                self._port = parsed.port
            except ValueError as e:
                raise ParseError("Invalid port: {}".format(e))

        scheme_has_port = (self._scheme in list(self._DEFAULT_PORTS) or
                           self._scheme is None)
        if self._port is not None and not scheme_has_port:
            raise ParseError("Ports are unsupported with {} scheme".format(
                self._scheme))

    def _matches_scheme(self, scheme: str) -> bool:
        return self._scheme is None or self._scheme == scheme

    def _matches_host(self, host: str) -> bool:
        # FIXME what about multiple dots?
        host = host.rstrip('.')

        # If we have no host in the match pattern, that means that we're
        # matching all hosts, which means we have a match no matter what the
        # test host is.
        # Contrary to Chromium, we don't need to check for
        # self._match_subdomains, as we want to return True here for e.g.
        # file:// as well.
        if self.host is None:
            return True

        # If the hosts are exactly equal, we have a match.
        if host == self.host:
            return True

        # Otherwise, we can only match if our match pattern matches subdomains.
        if not self._match_subdomains:
            return False

        # We don't do subdomain matching against IP addresses, so we can give
        # up now if the test host is an IP address.
        if not utils.raises(ValueError, ipaddress.ip_address, host):
            return False

        # Check if the test host is a subdomain of our host.
        if len(host) <= (len(self.host) + 1):
            return False

        if not host.endswith(self.host):
            return False

        return host[len(host) - len(self.host) - 1] == '.'

    def _matches_port(self, scheme: str, port: int) -> bool:
        if port == -1 and scheme in self._DEFAULT_PORTS:
            port = self._DEFAULT_PORTS[scheme]
        return self._port is None or self._port == port

    def _matches_path(self, path: str) -> bool:
        if self._path is None:
            return True

        # Match 'google.com' with 'google.com/'
        if path + '/*' == self._path:
            return True

        # FIXME Chromium seems to have a more optimized glob matching which
        # doesn't rely on regexes. Do we need that too?
        return fnmatch.fnmatchcase(path, self._path)

    def matches(self, qurl: QUrl) -> bool:
        """Check if the pattern matches the given QUrl."""
        qtutils.ensure_valid(qurl)

        if self._match_all:
            return True

        if not self._matches_scheme(qurl.scheme()):
            return False
        # FIXME ignore for file:// like Chromium?
        if not self._matches_host(qurl.host()):
            return False
        if not self._matches_port(qurl.scheme(), qurl.port()):
            return False
        if not self._matches_path(qurl.path()):
            return False

        return True
