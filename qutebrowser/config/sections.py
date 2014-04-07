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

import logging
from collections import OrderedDict

import qutebrowser.config.conftypes as conftypes


class KeyValue:

    """Representation of a section with ordinary key-value mappings.

    This is a section which contains normal "key = value" pairs with a fixed
    set of keys.

    Attributes:
        values: An OrderedDict with key as index and value as value.
                key: string
                value: SettingValue
        descriptions: A dict with the description strings for the keys.

    """

    def __init__(self, *args):
        """Constructor.

        Args:
            *args: Key/Value pairs to set.
                   key: string
                   value: SettingValue

        """
        if args:
            self.descriptions = {}
            self.values = OrderedDict()
            for (k, settingval, desc) in args:
                self.values[k] = settingval
                self.descriptions[k] = desc

    def __getitem__(self, key):
        """Get the value for key.

        Args:
            key: The key to get a value for, as a string.

        Return:
            The value, as value class.

        """
        return self.values[key]

    def __setitem__(self, key, value):
        """Set the value for key.

        Args:
            key: The key to set the value for, as a string.
            value: The value to set, as a string

        """
        self.values[key].value = value

    def __iter__(self):
        """Iterate over all set values."""
        # FIXME using a custom iterator this could be done more efficiently.
        return self.values.__iter__()

    def __bool__(self):
        """Get boolean state."""
        return bool(self.values)

    def items(self):
        """Get dict item tuples."""
        return self.values.items()

    def from_cp(self, sect):
        """Initialize the values from a configparser section."""
        for k, v in sect.items():
            logging.debug("'{}' = '{}'".format(k, v))
            self.values[k].rawvalue = v


class ValueList:

    """This class represents a section with a list key-value settings.

    These are settings inside sections which don't have fixed keys, but instead
    have a dynamic list of "key = value" pairs, like keybindings or
    searchengines.

    They basically consist of two different SettingValues and have no defaults.

    Attributes:
        values: An OrderedDict with key as index and value as value.
        default: An OrderedDict with the default configuration as strings.
        types: A tuple for (keytype, valuetype)
        valdict: The "true value" dict.
        #descriptions: A dict with the description strings for the keys.
        #              Currently a global empty dict to be compatible with
        #              KeyValue section.

    """

    values = None
    default = None
    types = None
    #descriptions = {}

    def __init__(self):
        """Wrap types over default values. Take care when overriding this."""
        self.values = OrderedDict()
        self.default = OrderedDict(
            [(key, conftypes.SettingValue(self.types[1], value))
             for key, value in self.default.items()])
        self.valdict = OrderedDict()

    def update_valdict(self):
        """Update the global "true" value dict."""
        self.valdict.clear()
        self.valdict.update(self.default)
        if self.values is not None:
            self.valdict.update(self.values)

    def __getitem__(self, key):
        """Get the value for key.

        Args:
            key: The key to get a value for, as a string.

        Return:
            The value, as value class.

        """
        try:
            return self.values[key]
        except KeyError:
            return self.default[key]

    def __iter__(self):
        """Iterate over all set values."""
        # FIXME using a custon iterator this could be done more efficiently
        self.update_valdict()
        return self.valdict.__iter__()

    def __bool__(self):
        """Get boolean state of section."""
        self.update_valdict()
        return bool(self.valdict)

    def items(self):
        """Get dict items."""
        self.update_valdict()
        return self.valdict.items()

    def from_cp(self, sect):
        """Initialize the values from a configparser section."""
        keytype = self.types[0]()
        valtype = self.types[1]()
        for k, v in sect.items():
            keytype.validate(k)
            valtype.validate(v)
            self.values[k] = conftypes.SettingValue(self.types[1], v)


class SearchEngines(ValueList):

    """Search engine config section."""

    types = (conftypes.SearchEngineName, conftypes.SearchEngineUrl)
    # FIXME how to handle interpolation here?
    default = OrderedDict([
        ('DEFAULT', '${duckduckgo}'),
        ('duckduckgo', 'https://duckduckgo.com/?q={}'),
        ('ddg', '${duckduckgo}'),
        ('google', 'https://encrypted.google.com/search?q={}'),
        ('g', '${google}'),
        ('wikipedia', 'http://en.wikipedia.org/w/index.php?'
                      'title=Special:Search&search={}'),
        ('wiki', '${wikipedia}'),
    ])


class KeyBindings(ValueList):

    """Keybindings config section."""

    types = (conftypes.KeyBindingName, conftypes.KeyBinding)
    default = OrderedDict([
        ('o', 'open'),
        ('go', 'opencur'),
        ('O', 'tabopen'),
        ('gO', 'tabopencur'),
        ('ga', 'tabopen about:blank'),
        ('d', 'tabclose'),
        ('J', 'tabnext'),
        ('K', 'tabprev'),
        ('r', 'reload'),
        ('H', 'back'),
        ('L', 'forward'),
        ('h', 'scroll -50 0'),
        ('j', 'scroll 0 50'),
        ('k', 'scroll 0 -50'),
        ('l', 'scroll 50 0'),
        ('u', 'undo'),
        ('gg', 'scroll_perc_y 0'),
        ('G', 'scroll_perc_y'),
        ('n', 'nextsearch'),
        ('yy', 'yank'),
        ('yY', 'yank sel'),
        ('yt', 'yanktitle'),
        ('yT', 'yanktitle sel'),
        ('pp', 'paste'),
        ('pP', 'paste sel'),
        ('Pp', 'tabpaste'),
        ('PP', 'tabpaste sel'),
        ('-', 'zoomout'),
        ('+', 'zoomin'),
        ('@Ctrl-Q@', 'quit'),
        ('@Ctrl-Shift-T@', 'undo'),
        ('@Ctrl-W@', 'tabclose'),
        ('@Ctrl-T@', 'tabopen about:blank'),
        ('@Ctrl-F@', 'scroll_page 0 1'),
        ('@Ctrl-B@', 'scroll_page 0 -1'),
        ('@Ctrl-D@', 'scroll_page 0 0.5'),
        ('@Ctrl-U@', 'scroll_page 0 -0.5'),
    ])


class Aliases(ValueList):

    """Aliases config section."""

    types = (conftypes.Command, conftypes.Command)
    default = OrderedDict()
