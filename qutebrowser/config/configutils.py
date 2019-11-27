# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Utilities and data structures used by various config code."""


import typing
import collections
import itertools
import operator

import attr
from PyQt5.QtCore import QUrl

from qutebrowser.utils import utils, urlmatch, urlutils
from qutebrowser.config import configexc

if typing.TYPE_CHECKING:
    from qutebrowser.config import configdata


class Unset:

    """Sentinel object."""

    __slots__ = ()

    def __repr__(self) -> str:
        return '<UNSET>'


UNSET = Unset()


@attr.s(frozen=True)
class ScopedValue:

    """A configuration value which is valid for a UrlPattern.

    Attributes:
        value: The value itself.
        pattern: The UrlPattern for the value, or None for global values.
    """

    value = attr.ib()  # type: typing.Any
    pattern = attr.ib()  # type: typing.Optional[urlmatch.UrlPattern]
    # An increasing counter of order this value was inserted in.
    insert_id = attr.ib()  # type: int


class Values:

    """A collection of values for a single setting.

    Currently, we store patterns in two dictionaries for different types of
    lookups. A ordered, pattern keyed map, and an unordered, domain keyed map.

    This means that finding a value based on a pattern is fast, and matching
    url patterns is fast if all domains are unique.

    If there are many patterns under the domain (or subdomain) that is being
    evaluated, or any patterns that cannot have a concrete domain found, this
    will become slow again.

    Attributes:
        opt: The Option being customized.
        values: A list of ScopedValues to start with.

    """

    _VmapKeyType = typing.Optional[urlmatch.UrlPattern]

    def __init__(self,
                 opt: 'configdata.Option',
                 values: typing.Sequence[ScopedValue] = ()) -> None:
        self.opt = opt
        self._vmap = collections.OrderedDict()  \
            # type: collections.OrderedDict[Values._VmapKeyType, ScopedValue]
        # A map from domain parts to rules that fall under them.
        self._domain_map = collections.defaultdict(set)  \
            # type: typing.Dict[typing.Optional[str], typing.Set[ScopedValue]]
        self._scoped_id = 0

        for v in values:
            self.add(value=v.value, pattern=v.pattern)

    def __repr__(self) -> str:
        return utils.get_repr(self, opt=self.opt,
                              values=list(self._vmap.values()),
                              constructor=True)

    def __str__(self) -> str:
        """Get the values as human-readable string."""
        if not self:
            return '{}: <unchanged>'.format(self.opt.name)

        lines = []
        for scoped in self._vmap.values():
            str_value = self.opt.typ.to_str(scoped.value)
            if scoped.pattern is None:
                lines.append('{} = {}'.format(self.opt.name, str_value))
            else:
                lines.append('{}: {} = {}'.format(
                    scoped.pattern, self.opt.name, str_value))
        return '\n'.join(lines)

    def __iter__(self) -> typing.Iterator['ScopedValue']:
        """Yield ScopedValue elements.

        This yields in "normal" order, i.e. global and then first-set settings
        first.
        """
        yield from self._vmap.values()

    def __bool__(self) -> bool:
        """Check whether this value is customized."""
        return bool(self._vmap)

    def _check_pattern_support(
            self, arg: typing.Optional[urlmatch.UrlPattern]) -> None:
        """Make sure patterns are supported if one was given."""
        if arg is not None and not self.opt.supports_pattern:
            raise configexc.NoPatternError(self.opt.name)

    def add(self, value: typing.Any,
            pattern: urlmatch.UrlPattern = None) -> None:
        """Add a value with the given pattern to the list of values."""
        self._check_pattern_support(pattern)
        self.remove(pattern)
        scoped = ScopedValue(value, pattern, self._scoped_id)
        self._scoped_id += 1
        self._vmap[pattern] = scoped

        host = pattern.host if pattern else None
        self._domain_map[host].add(scoped)

    def remove(self, pattern: urlmatch.UrlPattern = None) -> bool:
        """Remove the value with the given pattern.

        If a matching pattern was removed, True is returned.
        If no matching pattern was found, False is returned.
        """
        self._check_pattern_support(pattern)
        if pattern not in self._vmap:
            return False

        host = pattern.host if pattern else None
        scoped_value = self._vmap[pattern]
        # If we error here, that means domain_map and vmap are out of sync,
        # report a bug!
        assert host in self._domain_map
        self._domain_map[host].remove(scoped_value)
        del self._vmap[pattern]
        return True

    def clear(self) -> None:
        """Clear all customization for this value."""
        self._vmap.clear()
        self._domain_map.clear()
        self._scoped_id = 0

    def _get_fallback(self, fallback: bool) -> typing.Any:
        """Get the fallback global/default value."""
        if None in self._vmap:
            return self._vmap[None].value

        if fallback:
            return self.opt.default
        else:
            return UNSET

    def get_for_url(self, url: QUrl = None, *,
                    fallback: bool = True) -> typing.Any:
        """Get a config value, falling back when needed.

        This first tries to find a value matching the URL (if given).
        If there's no match:
          With fallback=True, the global/default setting is returned.
          With fallback=False, UNSET is returned.
        """
        self._check_pattern_support(url)
        candidates = []  # type: typing.List[ScopedValue]
        if url is not None:
            # We must check the 'None' key as well, in case any patterns that
            # did not have a domain match.
            widened_hosts = (
                None,)  # type: typing.Iterable[typing.Optional[str]]
            domains_len = len(self._domain_map)
            if None in self._domain_map:
                domains_len -= 1
            # Only compute widened domains if we have any non-domain matches
            # to possibly hit.
            if domains_len > 0:
                widened_hosts = itertools.chain(
                    urlutils.widened_hostnames(url.host()),
                    widened_hosts)
            for host in widened_hosts:
                host_set = self._domain_map.get(host, ())
                for scoped in host_set:
                    if (scoped.pattern is not None and
                            scoped.pattern.matches(url)):
                        candidates.append(scoped)
            if candidates:
                return max(
                    candidates, key=operator.attrgetter('insert_id')).value

            if not fallback:
                return UNSET

        return self._get_fallback(fallback)

    def get_for_pattern(self,
                        pattern: typing.Optional[urlmatch.UrlPattern], *,
                        fallback: bool = True) -> typing.Any:
        """Get a value only if it's been overridden for the given pattern.

        This is useful when showing values to the user.

        If there's no match:
          With fallback=True, the global/default setting is returned.
          With fallback=False, UNSET is returned.
        """
        self._check_pattern_support(pattern)
        if pattern is not None:
            if pattern in self._vmap:
                return self._vmap[pattern].value

            if not fallback:
                return UNSET

        return self._get_fallback(fallback)
