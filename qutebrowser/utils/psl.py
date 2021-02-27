# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2021 Javier Ayres <javier@lufte.net>
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

import enum
import os.path

from PyQt5.QtCore import QUrl

from qutebrowser.utils import standarddir, urlutils


class PSLNotFound(Exception):
    """Raised when no public_suffix_list.dat file is found.

    Attributes:
        paths: iterable of all tried paths.
    """

    def __init__(self, paths):
        super().__init__(
            "Couldn't find public_suffix_list.dat in any of the expected paths: "
            "{}".format(', '.join(paths))
        )


class _Rule(enum.Enum):

    NORMAL = enum.auto()
    WILDCARD = enum.auto()
    EXCEPTION = enum.auto()


def _widened_hostnames(hostname):
    """A generator for widening string hostnames.

    Ex: a.c.foo -> [a.c.foo, c.foo, foo]"""
    while hostname:
        yield hostname
        hostname = hostname.partition(".")[-1]


class _SuffixList:

    _rules = None

    def _load_rules(self) -> None:
        PSL_PATHS = (
            # User-provided list in data directory (need to wait until standarddir is
            # initialized)
            os.path.join(standarddir.data(), 'public_suffix_list.dat'),
            # Bundled list
            os.path.join(__file__, '../public_suffix_list.dat'),
            # Debian publicsuffix package
            '/usr/share/publicsuffix/public_suffix_list.dat'
        )
        path = None
        for psl_path in PSL_PATHS:
            if os.path.exists(psl_path):
                path = psl_path
                break
        if not path:
            raise PSLNotFound(PSL_PATHS)

        self._rules = {}
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('//') or not line:
                    continue
                if line.startswith('*.'):
                    self._rules[line[2:]] = _Rule.WILDCARD
                elif line.startswith('!'):
                    self._rules[line[1:]] = _Rule.EXCEPTION
                else:
                    assert '*' not in line and '!' not in line, line
                    self._rules[line] = _Rule.NORMAL

    @property
    def rules(self):
        if self._rules is None:
            self._load_rules()
        return self._rules

    def sld(self, url: QUrl) -> str:
        urlutils.ensure_valid(url)
        host = url.host()

        if '.' not in host or self.rules.get(host) in (_Rule.NORMAL, _Rule.WILDCARD):
            return None  # FIXME why?
            # If the hostname doesn't have a dot it's either a tld, which doesn't have
            # a sld, or it doesn't match any rule, in which case the prevailing rule is
            # '*' according to https://publicsuffix.org/list/. If the hostname has a dot
            # but matches a normal/wildcard rule, it's a tld.

        parts = list(_widened_hostnames(host))

        for i, part in enumerate(parts):
            rule = self.rules.get(part)
            if rule == _Rule.EXCEPTION:
                return parts[i]
            elif rule == _Rule.NORMAL:
                return parts[i - 1]
            elif rule == _Rule.WILDCARD:
                return parts[i - 2] if i >= 2 else None

        return parts[-2]

    def same_domain(self, url1: QUrl, url2: QUrl) -> bool:
        """Check if url1 and url2 belong to the same website.

        If the URL's schemes or ports are different, they are always treated as not
        equal.

        Return:
            True if the domains are the same, False otherwise.
        """
        if url1.scheme() != url2.scheme() or url1.port() != url2.port():
            return False

        sld1 = self.sld(url1)
        sld2 = self.sld(url2)
        if not sld1:
            return url1.host() == url2.host()

        return sld1 == sld2


suffix_list = _SuffixList()
