# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Setting sections used for qutebrowser."""

import collections

from qutebrowser.config import value as confvalue


class Section:

    """Base class for KeyValue/ValueList sections.

    Attributes:
        _readonly: Whether this section is read-only.
        values: An OrderedDict with key as index and value as value.
                key: string
                value: SettingValue
        descriptions: A dict with the description strings for the keys.
    """

    def __init__(self):
        self.values = None
        self.descriptions = {}
        self._readonly = False

    def __getitem__(self, key):
        """Get the value for key.

        Args:
            key: The key to get a value for, as a string.

        Return:
            The value, as value class.
        """
        return self.values[key]

    def __iter__(self):
        """Iterate over all set values."""
        return iter(self.values)

    def __bool__(self):
        """Get boolean state of section."""
        return bool(self.values)

    def __contains__(self, key):
        """Return whether the section contains a given key."""
        return key in self.values

    def items(self):
        """Get dict items."""
        return self.values.items()

    def keys(self):
        """Get value keys."""
        return self.values.keys()

    def delete(self, key):
        """Delete item with given key."""
        del self.values[key]

    def setv(self, layer, key, value, interpolated):
        """Set the value on a layer.

        Args:
            layer: The layer to set the value on, an element name of the
                   ValueLayers dict.
            key: The key of the element to set.
            value: The value to set.
            interpolated: The interpolated value, for checking, or None.
        """
        raise NotImplementedError

    def dump_userconfig(self):
        """Dump the part of the config which was changed by the user.

        Return:
            A list of (key, valuestr) tuples.
        """
        raise NotImplementedError


class KeyValue(Section):

    """Representation of a section with ordinary key-value mappings.

    This is a section which contains normal "key = value" pairs with a fixed
    set of keys.
    """

    def __init__(self, *defaults, readonly=False):
        """Constructor.

        Args:
            *defaults: A (key, value, description) list of defaults.
            readonly: Whether this config is readonly.
        """
        super().__init__()
        self._readonly = readonly
        if not defaults:
            return
        self.values = collections.OrderedDict()
        for (k, v, desc) in defaults:
            assert k not in self.values, k
            self.values[k] = v
            self.descriptions[k] = desc

    def setv(self, layer, key, value, interpolated):
        if self._readonly:
            raise ValueError("Trying to modify a read-only config!")
        self.values[key].setv(layer, value, interpolated)

    def dump_userconfig(self):
        changed = []
        for k, v in self.items():
            vals = v.values
            if vals['temp'] is not None and vals['temp'] != vals['default']:
                changed.append((k, vals['temp']))
            elif vals['conf'] is not None and vals['conf'] != vals['default']:
                changed.append((k, vals['conf']))
        return changed


class ValueList(Section):

    """This class represents a section with a list key-value settings.

    These are settings inside sections which don't have fixed keys, but instead
    have a dynamic list of "key = value" pairs, like key bindings or
    searchengines.

    They basically consist of two different SettingValues.

    Attributes:
        layers: An OrderedDict of the config layers.
        keytype: The type to use for the key (only used for validating)
        valtype: The type to use for the value.
        _ordered_value_cache: A ChainMap-like OrderedDict of all values.
        _readonly: Whether this section is read-only.
    """

    def __init__(self, keytype, valtype, *defaults, readonly=False):
        """Wrap types over default values. Take care when overriding this.

        Args:
            keytype: The type instance to be used for keys.
            valtype: The type instance to be used for values.
            *defaults: A (key, value) list of default values.
            readonly: Whether this config is readonly.
        """
        super().__init__()
        self._readonly = readonly
        self._ordered_value_cache = None
        self.keytype = keytype
        self.valtype = valtype
        self.layers = collections.OrderedDict([
            ('default', collections.OrderedDict()),
            ('conf', collections.OrderedDict()),
            ('temp', collections.OrderedDict()),
        ])
        defaultlayer = self.layers['default']
        for key, value in defaults:
            assert key not in defaultlayer, key
            defaultlayer[key] = confvalue.SettingValue(valtype, value)
        self.values = collections.ChainMap(
            self.layers['temp'], self.layers['conf'], self.layers['default'])

    def _ordered_values(self):
        """Get ordered values in layers.

        This is more expensive than the ChainMap, but we need this for
        iterating/items/etc. when order matters.
        """
        if self._ordered_value_cache is None:
            self._ordered_value_cache = collections.OrderedDict()
            for layer in self.layers.values():
                self._ordered_value_cache.update(layer)
        return self._ordered_value_cache

    def setv(self, layer, key, value, interpolated):
        if self._readonly:
            raise ValueError("Trying to modify a read-only config!")
        self.keytype.validate(key)
        if key in self.layers[layer]:
            self.layers[layer][key].setv(layer, value, interpolated)
        else:
            val = confvalue.SettingValue(self.valtype)
            val.setv(layer, value, interpolated)
            self.layers[layer][key] = val
        self._ordered_value_cache = None

    def dump_userconfig(self):
        changed = []
        mapping = collections.ChainMap(self.layers['temp'],
                                       self.layers['conf'])
        for k, v in mapping.items():
            try:
                if v.value() != self.layers['default'][k].value():
                    changed.append((k, v.value()))
            except KeyError:
                changed.append((k, v.value()))
        return changed

    def __iter__(self):
        """Iterate over all set values."""
        return self._ordered_values().__iter__()

    def items(self):
        """Get dict items."""
        return self._ordered_values().items()

    def keys(self):
        """Get value keys."""
        return self._ordered_values().keys()
