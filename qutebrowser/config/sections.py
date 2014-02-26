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

from collections import OrderedDict

import qutebrowser.config.templates as template
import qutebrowser.config.options as opt


class KeyValue:

    """Representation of a section with ordinary key-value mappings.

    This is a section which contains normal "key = value" pairs with a fixed
    set of keys.

    Attributes:
        values: An OrderedDict with key as index and value as value.
                key: string
                value: SettingValue

    """

    def __init__(self, *args):
        """Constructor.

        Args:
            *args: Key/Value pairs to set.
                   key: string
                   value: SettingValue

        """
        if args:
            self.values = OrderedDict(args)

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
        # FIXME using a custon iterator this could be done more efficiently
        return self.values.__iter__()

    def items(self):
        """Get dict item tuples."""
        return self.values.items()


class SearchEngines(template.ValueListSection):

    """Search engine config section."""

    types = (opt.SearchEngineName, opt.SearchEngineUrl)
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


class KeyBindings(template.ValueListSection):

    """Keybindings config section."""

    types = (opt.KeyBindingName, opt.KeyBinding)
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


class Aliases(template.ValueListSection):

    """Aliases config section."""

    types = (template.CommandSettingValue, template.CommandSettingValue)
    default = OrderedDict()
