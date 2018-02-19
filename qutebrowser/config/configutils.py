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


"""Utilities and data structures used by various config code."""


import attr


# Sentinel object
UNSET = object()


@attr.s
class ScopedValue:

    """A configuration value which is valid for a UrlPattern.

    Attributes:
        value: The value itself.
        pattern: The UrlPattern for the value, or None for global values.
    """

    value = attr.ib()
    pattern = attr.ib()


class Values:

    """A collection of values for a single setting.

    Currently, this is a list and iterates through all possible ScopedValues to
    find matching ones.

    In the future, it should be possible to optimize this by doing
    pre-selection based on hosts, by making this a dict mapping the
    non-wildcard part of the host to a list of matching ScopedValues.

    That way, when searching for a setting for sub.example.com, we only have to
    check 'sub.example.com', 'example.com', '.com' and '' instead of checking
    all ScopedValues for the given setting.

    Attributes:
        _opt: The Option being customized.
    """

    def __init__(self, opt):
        self._opt = opt
        self._values = []

    def __iter__(self):
        """Yield ScopedValue elements.

        This yields in "normal" order, i.e. global and then first-set settings
        first.
        """
        yield from self._values

    def add(self, value, pattern=None):
        """Add a value with the given pattern to the list of values.

        Currently, we just add this to the end of the list, meaning the same
        pattern can be in there multiple times. However, that avoids doing a
        search through all values every time a setting is set. We can still
        optimize this later when changing the data structure as mentioned in
        the class docstring.
        """
        scoped = ScopedValue(value, pattern)
        self._values.append(scoped)

    def remove(self, pattern=None):
        """Remove the value with the given pattern."""
        # FIXME:conf Should this ignore patterns which weren't found?
        self._values = [v for v in self._values if v.pattern != pattern]

    def clear(self):
        """Clear all customization for this value."""
        self._values = []

    def _get_fallback(self):
        """Get the fallback global/default value."""
        if self._values:
            scoped = self._values[-1]
            if scoped.pattern is None:
                # It's possible that the setting is only customized from the
                # default for a given URL.
                return scoped.value

        return self._opt.default

    def get_for_url(self, url=None, *, fallback=True):
        """Get a config value, falling back when needed.

        This first tries to find a value matching the URL (if given).
        If there's no match:
          With fallback=True, the global/default setting is returned.
          With fallback=False, UNSET is returned.
        """
        if url is not None:
            for scoped in reversed(self._values):
                if scoped.pattern is not None and scoped.pattern.matches(url):
                    return scoped.value

            if not fallback:
                return UNSET

        return self._get_fallback()

    def get_for_pattern(self, pattern, *, fallback=True):
        """Get a value only if it's been overridden for the given pattern.

        This is useful when showing values to the user.

        If there's no match:
          With fallback=True, the global/default setting is returned.
          With fallback=False, UNSET is returned.
        """
        if pattern is not None:
            for scoped in reversed(self._values):
                if scoped.pattern == pattern:
                    return scoped.value

            if not fallback:
                return UNSET

        return self._get_fallback()
