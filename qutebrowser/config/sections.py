# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from collections import OrderedDict, ChainMap

from qutebrowser.config.value import SettingValue


class Section:

    """Base class for KeyValue/ValueList sections.

    Attributes:
        values: An OrderedDict with key as index and value as value.
                key: string
                value: SettingValue
        descriptions: A dict with the description strings for the keys.
    """

    def __init__(self):
        self.values = None
        self.descriptions = {}

    def __getitem__(self, key):
        """Get the value for key.

        Args:
            key: The key to get a value for, as a string.

        Return:
            The value, as value class.
        """
        return self.values[key]

    def __setitem__(self, key, value):
        """Set the config value for key.

        Args:
            key: The key to set the value for, as a string.
            value: The value to set, as a string
        """
        self.setv('conf', key, value)

    def __iter__(self):
        """Iterate over all set values."""
        return self.values.__iter__()

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

    def setv(self, layer, key, value, interpolated):
        """Set the value on a layer.

        Args:
            layer: The layer to set the value on, an element name of the
                   ValueLayers dict.
            key: The key of the element to set.
            value: The value to set.
            interpolated: The interpolated value, for checking.
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

    def __init__(self, *defaults):
        """Constructor.

        Args:
            *defaults: A (key, value, description) list of defaults.
        """
        super().__init__()
        if not defaults:
            return
        self.values = OrderedDict()
        for (k, v, desc) in defaults:
            self.values[k] = v
            self.descriptions[k] = desc

    def setv(self, layer, key, value, interpolated):
        self.values[key].setv(layer, value, interpolated)

    def dump_userconfig(self):
        changed = []
        for k, v in self.items():
            if (v.values['temp'] is not None and
                    v.values['temp'] != v.values['default']):
                changed.append((k, v.values['temp']))
            elif (v.values['conf'] is not None and
                    v.values['conf'] != v.values['default']):
                changed.append((k, v.values['conf']))
        return changed


class ValueList(Section):

    """This class represents a section with a list key-value settings.

    These are settings inside sections which don't have fixed keys, but instead
    have a dynamic list of "key = value" pairs, like keybindings or
    searchengines.

    They basically consist of two different SettingValues.

    Attributes:
        default: An OrderedDict with the default configuration as strings.
        keytype: The type to use for the key (only used for validating)
        valtype: The type to use for the value.
        valdict: The "true value" dict.
    """

    # FIXME how to handle value layers here?

    def __init__(self, keytype, valtype, *defaults):
        """Wrap types over default values. Take care when overriding this.

        Args:
            keytype: The type to be used for keys.
            valtype: The type to be used for values.
            *defaults: A (key, value) list of default values.
        """
        super().__init__()
        self.keytype = keytype
        self.valtype = valtype
        self.layers = OrderedDict([
            ('default', OrderedDict([(key, SettingValue(valtype, value))
                                     for key, value in defaults])),
            ('conf', OrderedDict()),
            ('temp', OrderedDict()),
        ])
        self.values = ChainMap(self.layers['temp'], self.layers['conf'],
                               self.layers['default'])

    def setv(self, layer, key, value, interpolated):
        self.keytype().validate(key)
        if key in self.layers[layer]:
            self.layers[layer][key].setv(layer, value, interpolated)
        else:
            val = SettingValue(self.valtype)
            val.setv(layer, value, interpolated)
            self.layers[layer][key] = val

    def dump_userconfig(self):
        changed = []
        mapping = ChainMap(self.layers['temp'], self.layers['conf'])
        for k, v in mapping.items():
            if v.value != self.layers['default'][k].value:
                changed.append((k, v.value))
        return changed
