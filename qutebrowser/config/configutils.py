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


"""Utilities and data structures used by various config code."""


import typing
import collections
import itertools
import operator

from PyQt5.QtCore import QUrl

from qutebrowser.utils import utils, urlmatch, usertypes, qtutils
from qutebrowser.config import configexc

if typing.TYPE_CHECKING:
    from qutebrowser.config import configdata


def _widened_hostnames(hostname: str) -> typing.Iterable[str]:
    """A generator for widening string hostnames.

    Ex: a.c.foo -> [a.c.foo, c.foo, foo]"""
    while hostname:
        yield hostname
        hostname = hostname.partition(".")[-1]


class ScopedValue:

    """A configuration value which is valid for a UrlPattern.

    Attributes:
        value: The value itself.
        pattern: The UrlPattern for the value, or None for global values.
        hide_userconfig: Hide this customization from config.dump_userconfig().
    """

    id_gen = itertools.count(0)

    def __init__(self, value: typing.Any,
                 pattern: typing.Optional[urlmatch.UrlPattern],
                 hide_userconfig: bool = False) -> None:
        self.value = value
        self.pattern = pattern
        self.hide_userconfig = hide_userconfig
        self.pattern_id = next(ScopedValue.id_gen)

    def __repr__(self) -> str:
        return utils.get_repr(self, value=self.value, pattern=self.pattern,
                              hide_userconfig=self.hide_userconfig,
                              pattern_id=self.pattern_id)


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
        _vmap: A mapping of all pattern objects to ScopedValues.
        _domain_map: A mapping from hostnames to all associated ScopedValues.
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

        for scoped in values:
            self._add_scoped(scoped)

    def __repr__(self) -> str:
        return utils.get_repr(self, opt=self.opt,
                              values=list(self._vmap.values()),
                              constructor=True)

    def __str__(self) -> str:
        """Get the values as human-readable string."""
        lines = self.dump(include_hidden=True)
        if lines:
            return '\n'.join(lines)
        return '{}: <unchanged>'.format(self.opt.name)

    def dump(self, include_hidden: bool = False) -> typing.Sequence[str]:
        """Dump all customizations for this value.

        Arguments:
           include_hidden: Also show values with hide_userconfig=True.
        """
        lines = []

        for scoped in self._vmap.values():
            if scoped.hide_userconfig and not include_hidden:
                continue

            str_value = self.opt.typ.to_str(scoped.value)
            if scoped.pattern is None:
                lines.append('{} = {}'.format(self.opt.name, str_value))
            else:
                lines.append('{}: {} = {}'.format(
                    scoped.pattern, self.opt.name, str_value))

        return lines

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
            self, arg: typing.Union[urlmatch.UrlPattern, QUrl, None]) -> None:
        """Make sure patterns are supported if one was given."""
        if arg is not None and not self.opt.supports_pattern:
            raise configexc.NoPatternError(self.opt.name)

    def add(self, value: typing.Any,
            pattern: urlmatch.UrlPattern = None, *,
            hide_userconfig: bool = False) -> None:
        """Add a value with the given pattern to the list of values.

        If hide_userconfig is given, the value is hidden from
        config.dump_userconfig() and thus qute://configdiff.
        """
        scoped = ScopedValue(value, pattern, hide_userconfig=hide_userconfig)
        self._add_scoped(scoped)

    def _add_scoped(self, scoped: ScopedValue) -> None:
        """Add an existing ScopedValue object."""
        self._check_pattern_support(scoped.pattern)
        self.remove(scoped.pattern)

        self._vmap[scoped.pattern] = scoped

        host = scoped.pattern.host if scoped.pattern else None
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

    def _get_fallback(self, fallback: bool) -> typing.Any:
        """Get the fallback global/default value."""
        if None in self._vmap:
            return self._vmap[None].value

        if fallback:
            return self.opt.default
        else:
            return usertypes.UNSET

    def get_for_url(self, url: QUrl = None, *,
                    fallback: bool = True) -> typing.Any:
        """Get a config value, falling back when needed.

        This first tries to find a value matching the URL (if given).
        If there's no match:
          With fallback=True, the global/default setting is returned.
          With fallback=False, usertypes.UNSET is returned.
        """
        self._check_pattern_support(url)
        if url is None:
            return self._get_fallback(fallback)
        qtutils.ensure_valid(url)

        candidates = []  # type: typing.List[ScopedValue]
        # Urls trailing with '.' are equivalent to non-trailing types.
        # urlutils strips them, so in order to match we will need to as well.
        widened_hosts = _widened_hostnames(url.host().rstrip('.'))
        # We must check the 'None' key as well, in case any patterns that
        # did not have a domain match.
        for host in itertools.chain(widened_hosts, [None]):
            host_set = self._domain_map.get(host, ())
            for scoped in host_set:
                if scoped.pattern is not None and scoped.pattern.matches(url):
                    candidates.append(scoped)

        if candidates:
            scoped = max(candidates, key=operator.attrgetter('pattern_id'))
            return scoped.value

        if not fallback:
            return usertypes.UNSET

        return self._get_fallback(fallback)

    def get_for_pattern(self,
                        pattern: typing.Optional[urlmatch.UrlPattern], *,
                        fallback: bool = True) -> typing.Any:
        """Get a value only if it's been overridden for the given pattern.

        This is useful when showing values to the user.

        If there's no match:
          With fallback=True, the global/default setting is returned.
          With fallback=False, usertypes.UNSET is returned.
        """
        self._check_pattern_support(pattern)
        if pattern is not None:
            if pattern in self._vmap:
                return self._vmap[pattern].value

            if not fallback:
                return usertypes.UNSET

        return self._get_fallback(fallback)


class FontFamilies:

    """A list of font family names."""

    def __init__(self, families: typing.Sequence[str]) -> None:
        self._families = families
        self.family = families[0] if families else None

    def __iter__(self) -> typing.Iterator[str]:
        yield from self._families

    def __repr__(self) -> str:
        return utils.get_repr(self, families=self._families, constructor=True)

    def __str__(self) -> str:
        return self.to_str()

    def _quoted_families(self) -> typing.Iterator[str]:
        for f in self._families:
            needs_quoting = any(c in f for c in ', ')
            yield '"{}"'.format(f) if needs_quoting else f

    def to_str(self, *, quote: bool = True) -> str:
        families = self._quoted_families() if quote else self._families
        return ', '.join(families)

    @classmethod
    def from_str(cls, family_str: str) -> 'FontFamilies':
        """Parse a CSS-like string of font families."""
        families = []

        for part in family_str.split(','):
            part = part.strip()

            # The Qt CSS parser handles " and ' before passing the string to
            # QFont.setFamily.
            if ((part.startswith("'") and part.endswith("'")) or
                    (part.startswith('"') and part.endswith('"'))):
                part = part[1:-1]

            if not part:
                continue

            families.append(part)

        return cls(families)
