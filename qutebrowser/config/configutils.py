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
import textwrap

from qutebrowser.utils import utils
from qutebrowser.config import configexc


class _UnsetObject:

    """Sentinel object."""

    __slots__ = ()

    def __repr__(self):
        return '<UNSET>'


UNSET = _UnsetObject()


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
        opt: The Option being customized.
    """

    def __init__(self, opt, values=None):
        self.opt = opt
        self._values = values or []

    def __repr__(self):
        return utils.get_repr(self, opt=self.opt, values=self._values,
                              constructor=True)

    def __str__(self):
        """Get the values as human-readable string."""
        if not self:
            return '{}: <unchanged>'.format(self.opt.name)

        lines = []
        for scoped in self._values:
            str_value = self.opt.typ.to_str(scoped.value)
            if scoped.pattern is None:
                lines.append('{} = {}'.format(self.opt.name, str_value))
            else:
                lines.append('{}: {} = {}'.format(
                    scoped.pattern, self.opt.name, str_value))
        return '\n'.join(lines)

    def __iter__(self):
        """Yield ScopedValue elements.

        This yields in "normal" order, i.e. global and then first-set settings
        first.
        """
        yield from self._values

    def __bool__(self):
        """Check whether this value is customized."""
        return bool(self._values)

    def _check_pattern_support(self, arg):
        """Make sure patterns are supported if one was given."""
        if arg is not None and not self.opt.supports_pattern:
            raise configexc.NoPatternError(self.opt.name)

    def add(self, value, pattern=None):
        """Add a value with the given pattern to the list of values."""
        self._check_pattern_support(pattern)
        self.remove(pattern)
        scoped = ScopedValue(value, pattern)
        self._values.append(scoped)

    def remove(self, pattern=None):
        """Remove the value with the given pattern.

        If a matching pattern was removed, True is returned.
        If no matching pattern was found, False is returned.
        """
        self._check_pattern_support(pattern)
        old_len = len(self._values)
        self._values = [v for v in self._values if v.pattern != pattern]
        return old_len != len(self._values)

    def clear(self):
        """Clear all customization for this value."""
        self._values = []

    def _get_fallback(self, fallback):
        """Get the fallback global/default value."""
        for scoped in self._values:
            if scoped.pattern is None:
                return scoped.value

        if fallback:
            return self.opt.default
        else:
            return UNSET

    def get_for_url(self, url=None, *, fallback=True):
        """Get a config value, falling back when needed.

        This first tries to find a value matching the URL (if given).
        If there's no match:
          With fallback=True, the global/default setting is returned.
          With fallback=False, UNSET is returned.
        """
        self._check_pattern_support(url)
        if url is not None:
            for scoped in reversed(self._values):
                if scoped.pattern is not None and scoped.pattern.matches(url):
                    return scoped.value

            if not fallback:
                return UNSET

        return self._get_fallback(fallback)

    def get_for_pattern(self, pattern, *, fallback=True):
        """Get a value only if it's been overridden for the given pattern.

        This is useful when showing values to the user.

        If there's no match:
          With fallback=True, the global/default setting is returned.
          With fallback=False, UNSET is returned.
        """
        self._check_pattern_support(pattern)
        if pattern is not None:
            for scoped in reversed(self._values):
                if scoped.pattern == pattern:
                    return scoped.value

            if not fallback:
                return UNSET

        return self._get_fallback(fallback)


class ConfigPyGenerator:

    """Generator of config.py-like strings from given settings."""

    def __init__(self, options, bindings, *, commented):
        self._options = options
        self._bindings = bindings
        self._commented = commented

    def _line(self, line):
        """Get an (optionally commented) line."""
        if self._commented:
            if line.startswith('#'):
                return '#' + line
            else:
                return '# ' + line
        else:
            return line

    def gen_text(self):
        return '\n'.join(self._gen_lines())

    def _gen_lines(self):
        """Generate a config.py with the given settings/bindings.

        Yields individual lines.
        """
        yield from self._gen_header()
        yield from self._gen_options()
        yield from self._gen_bindings()

    def _gen_header(self):
        """Generate the initial header of the config."""
        yield self._line("# Autogenerated config.py")
        yield self._line("# Documentation:")
        yield self._line("#   qute://help/configuring.html")
        yield self._line("#   qute://help/settings.html")
        yield ''
        if self._commented:
            # When generated from an autoconfig.yml with commented=False,
            # we don't want to load that autoconfig.yml anymore.
            yield self._line("# This is here so configs done via the GUI are "
                             "still loaded.")
            yield self._line("# Remove it to not load settings done via the "
                             "GUI.")
            yield self._line("config.load_autoconfig()")
            yield ''
        else:
            yield self._line("# Uncomment this to still load settings "
                             "configured via autoconfig.yml")
            yield self._line("# config.load_autoconfig()")
            yield ''

    def _gen_options(self):
        """Generate the options part of the config."""
        for pattern, opt, value in self._options:
            if opt.name in ['bindings.commands', 'bindings.default']:
                continue

            for line in textwrap.wrap(opt.description):
                yield self._line("# {}".format(line))

            yield self._line("# Type: {}".format(opt.typ.get_name()))

            valid_values = opt.typ.get_valid_values()
            if valid_values is not None and valid_values.generate_docs:
                yield self._line("# Valid values:")
                for val in valid_values:
                    try:
                        desc = valid_values.descriptions[val]
                        yield self._line("#   - {}: {}".format(val, desc))
                    except KeyError:
                        yield self._line("#   - {}".format(val))

            if pattern is None:
                yield self._line('c.{} = {!r}'.format(opt.name, value))
            else:
                yield self._line('config.set({!r}, {!r}, {!r})'.format(
                    opt.name, value, str(pattern)))
            yield ''

    def _gen_bindings(self):
        """Generate the bindings part of the config."""
        normal_bindings = self._bindings.pop('normal', {})
        if normal_bindings:
            yield self._line('# Bindings for normal mode')
            for key, command in sorted(normal_bindings.items()):
                yield self._line('config.bind({!r}, {!r})'.format(
                    key, command))
            yield ''

        for mode, mode_bindings in sorted(self._bindings.items()):
            yield self._line('# Bindings for {} mode'.format(mode))
            for key, command in sorted(mode_bindings.items()):
                yield self._line('config.bind({!r}, {!r}, mode={!r})'.format(
                    key, command, mode))
            yield ''
