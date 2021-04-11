# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2021 Javier Ayres (lufte) <javier@lufte.net>
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

"""Parser and loader for Mozilla's Public Suffix List."""

import enum
import os.path
from typing import Iterable, Optional, Dict

from PyQt5.QtCore import QUrl

from qutebrowser.utils import standarddir, urlutils, utils


class PSLNotFound(Exception):
    """Raised when no public_suffix_list.dat file is found.

    Attributes:
        paths: iterable of all tried paths.
    """

    def __init__(self, paths: Iterable[str]):
        super().__init__(
            "Couldn't find public_suffix_list.dat in any of the expected paths: "
            "{}".format(', '.join(paths))
        )


class _Rule(enum.Enum):

    NORMAL = enum.auto()
    WILDCARD = enum.auto()
    EXCEPTION = enum.auto()


class _SuffixList:

    _rules: Optional[Dict[str, _Rule]] = None

    def _load_rules(self) -> Dict[str, _Rule]:
        user_psl_path = os.path.join(standarddir.data(), 'public_suffix_list.dat')
        system_psl_paths = (
            '/usr/share/publicsuffix/public_suffix_list.dat',  # Debian's publicsuffix
        )
        bundled_psl_path = '3rdparty/public_suffix_list.dat'

        psl_file = None
        if os.path.exists(user_psl_path):
            with open(user_psl_path) as f:
                psl_file = f.read()
        else:
            try:
                psl_file = utils.read_file(bundled_psl_path)
            except FileNotFoundError:
                for path in system_psl_paths:
                    if os.path.exists(path):
                        with open(path) as f:
                            psl_file = f.read()
                        break

        if not psl_file:
            raise PSLNotFound((user_psl_path, bundled_psl_path) + system_psl_paths)

        rules = {}
        for line_number, line in enumerate(psl_file.splitlines()):
            line = line.strip()
            if line.startswith('//') or not line:
                continue
            if line.startswith('*.'):
                rules[line[2:]] = _Rule.WILDCARD
            elif line.startswith('!'):
                rules[line[1:]] = _Rule.EXCEPTION
            else:
                assert '*' not in line and '!' not in line, f'{line_number}: {line}'
                rules[line] = _Rule.NORMAL

        return rules

    @property
    def rules(self) -> Dict[str, _Rule]:
        if self._rules is None:
            self._rules = self._load_rules()
        return self._rules

    def sld(self, url: QUrl) -> Optional[str]:
        """Return the second-level domain of a URL."""
        urlutils.ensure_valid(url)
        host = url.host()

        if '.' not in host or self.rules.get(host) in (_Rule.NORMAL, _Rule.WILDCARD):
            return None
            # If the hostname doesn't have a dot it's either a tld, which doesn't have
            # a sld, or it doesn't match any rule, in which case the prevailing rule is
            # '*' according to https://publicsuffix.org/list/. If the hostname has a dot
            # but matches a normal/wildcard rule, it's a tld.

        parts = list(urlutils.widened_hostnames(host))

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
