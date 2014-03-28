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

"""Configuration data for config.py."""

from collections import OrderedDict

import qutebrowser.config.conftypes as types
import qutebrowser.config.sections as sect


FIRST_COMMENT = """
# vim: ft=dosini

# Configfile for qutebrowser.
#
# This configfile is parsed by python's configparser in extended
# interpolation mode. The format is very INI-like, so there are
# categories like [general] with "key = value"-pairs.
#
# Note that you shouldn't add your own comments, as this file is
# regenerated every time the config is saved.
#
# Interpolation looks like  ${value}  or  ${section:value} and will be
# replaced by the respective value.
#
# This is the default config, so if you want to remove anything from
# here (as opposed to change/add), for example a keybinding, set it to
# an empty value.
"""


SECTION_DESC = {
    'general': 'General/misc. options',
    'tabbar': 'Configuration of the tab bar.',
    'searchengines': (
        'Definitions of search engines which can be used via the address '
        'bar.\n'
        'The searchengine named DEFAULT is used when general.auto_search '
        'is true and something else than an URL was entered to be opened. '
        'Other search engines can be used via the bang-syntax, e.g. '
        '"qutebrowser !google". The string "{}" will be replaced by the '
        'search term, use "{{" and "}}" for literal {/} signs.'),
    'keybind': (
        "Bindings from a key(chain) to a command. For special keys (can't "
        'be part of a keychain), enclose them in @-signs. For modifiers, '
        'you can use either - or + as delimiters, and these names:\n'
        '  Control: Control, Ctrl\n'
        '  Meta:    Meta, Windows, Mod4\n'
        '  Alt:     Alt, Mod1\n'
        '  Shift:   Shift\n'
        'For simple keys (no @ signs), a capital letter means the key is '
        'pressed with Shift. For modifier keys (with @ signs), you need '
        'to explicitely add "Shift-" to match a key pressed with shift. '
        'You can bind multiple commands by separating them with ";;".'),
    'aliases': (
        'Here you can add aliases for commands. By default, no aliases '
        'are defined. Example which adds a new command :qtb to open '
        'qutebrowsers website:\n'
        '  qtb = open http://www.qutebrowser.org/'),
    'colors': (
        'Colors used in the UI. A value can be in one of the following '
        'format:\n'
        '  - #RGB/#RRGGBB/#RRRGGGBBB/#RRRRGGGGBBBB\n'
        '  - A SVG color name as specified in [1].\n'
        '  - transparent (no color)\n'
        '  - rgb(r, g, b) / rgba(r, g, b, a) (values 0-255 or '
        'percentages)\n'
        '  - hsv(h, s, v) / hsva(h, s, v, a) (values 0-255, hue 0-359)\n'
        '  - A gradient as explained at [2] under "Gradient"\n'
        '[1] http://www.w3.org/TR/SVG/types.html#ColorKeywords\n'
        '[2] http://qt-project.org/doc/qt-4.8/stylesheet-reference.html'
        '#list-of-property-types'),
    'fonts': (
        'Fonts used for the UI, with optional style/weight/size.\n'
        'Style: normal/italic/oblique\n'
        'Weight: normal, bold, 100..900\n'
        'Size: Number + px/pt\n'),
}


def configdata():
    """Get the config structure as an OrderedDict."""
    return OrderedDict([
        ('general', sect.KeyValue(
            ('show_completion',
             SettingValue(types.Bool, "true"),
             "Whether to show the autocompletion window or not."),

            ('completion_height',
             SettingValue(types.PercOrInt, "50%"),
             "The height of the completion, in px or as percentage of the "
             "window."),

            ('ignorecase',
             SettingValue(types.Bool, "true"),
             "Whether to do case-insensitive searching."),

            ('wrapsearch',
             SettingValue(types.Bool, "true"),
             "Whether to wrap search to the top when arriving at the end."),

            ('startpage',
             SettingValue(types.List, "http://www.duckduckgo.com"),
             "The default page(s) to open at the start, separated with "
             "commas."),

            ('auto_search',
             SettingValue(types.AutoSearch, "naive"),
             "Whether to start a search when something else than an URL is "
             "entered."),

            ('zoomlevels',
             SettingValue(types.IntList, "25,33,50,67,75,90,100,110,125,150,"
                                         "175,200,250,300,400,500"),
             "The available zoom levels, separated by commas."),

            ('defaultzoom',
             SettingValue(types.Int, "100"),
             "The default zoom level."),
        )),

        ('tabbar', sect.KeyValue(
            ('movable',
             SettingValue(types.Bool, "true"),
             "Whether tabs should be movable."),

            ('closebuttons',
             SettingValue(types.Bool, "false"),
             "Whether tabs should have close-buttons."),

            ('scrollbuttons',
             SettingValue(types.Bool, "true"),
             "Whether there should be scroll buttons if there are too many "
             "tabs."),

            ('position',
             SettingValue(types.Position, "north"),
             "The position of the tab bar."),

            ('select_on_remove',
             SettingValue(types.SelectOnRemove, "previous"),
             "Which tab to select when the focused tab is removed."),

            ('last_close',
             SettingValue(types.LastClose, "ignore"),
             "Behaviour when the last tab is closed."),
        )),

        ('searchengines', sect.SearchEngines()),

        ('keybind', sect.KeyBindings()),

        ('aliases', sect.Aliases()),

        ('colors', sect.KeyValue(
            ('completion.fg',
             SettingValue(types.Color, "#333333"),
             "Text color of the completion widget."),

            ('completion.item.bg',
             SettingValue(types.Color, "white"),
             "Background color of completion widget items."),

            ('completion.category.bg',
             SettingValue(
                 types.Color,
                 "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e4e4e4, "
                 "stop:1 #dbdbdb)"),
             "Background color of the completion widget category headers."),

            ('completion.category.border.top',
             SettingValue(types.Color, "#808080"),
             "Top border color of the completion widget category headers."),

            ('completion.category.border.bottom',
             SettingValue(types.Color, "#bbbbbb"),
             "Bottom border color of the completion widget category headers."),

            ('completion.item.selected.fg',
             SettingValue(types.Color, "#333333"),
             "Foreground color of the selected completion item."),

            ('completion.item.selected.bg',
             SettingValue(types.Color, "#ffec8b"),
             "Background color of the selected completion item."),

            ('completion.item.selected.border.top',
             SettingValue(types.Color, "#f2f2c0"),
             "Top border color of the completion widget category headers."),

            ('completion.item.selected.border.bottom',
             SettingValue(types.Color, "#ffec8b"),
             "Bottom border color of the selected completion item."),

            ('completion.match.fg',
             SettingValue(types.Color, "red"),
             "Foreground color of the matched text in the completion."),

            ('statusbar.bg',
             SettingValue(types.Color, "black"),
             "Foreground color of the statusbar."),

            ('statusbar.fg',
             SettingValue(types.Color, "white"),
             "Foreground color of the statusbar."),

            ('statusbar.bg.error',
             SettingValue(types.Color, "red"),
             "Background color of the statusbar if there was an error."),

            ('statusbar.fg.error',
             SettingValue(types.Color, "${statusbar.fg}"),
             "Foreground color of the statusbar if there was an error."),

            ('statusbar.progress.bg',
             SettingValue(types.Color, "white"),
             "Background color of the progress bar."),

            ('statusbar.url.fg',
             SettingValue(types.Color, "${statusbar.fg}"),
             "Default foreground color of the URL in the statusbar."),

            ('statusbar.url.fg.success',
             SettingValue(types.Color, "lime"),
             "Foreground color of the URL in the statusbar on successful "
             "load."),

            ('statusbar.url.fg.error',
             SettingValue(types.Color, "orange"),
             "Foreground color of the URL in the statusbar on error."),

            ('statusbar.url.fg.warn',
             SettingValue(types.Color, "yellow"),
             "Foreground color of the URL in the statusbar when there's a "
             "warning."),

            ('statusbar.url.fg.hover',
             SettingValue(types.Color, "aqua"),
             "Foreground color of the URL in the statusbar for hovered "
             "links."),

            ('tab.fg',
             SettingValue(types.Color, "white"),
             "Foreground color of the tabbar."),

            ('tab.bg',
             SettingValue(types.Color, "grey"),
             "Background color of the tabbar."),

            ('tab.bg.selected',
             SettingValue(types.Color, "black"),
             "Background color of the tabbar for the selected tab."),

            ('tab.seperator',
             SettingValue(types.Color, "white"),
             "Color for the tab seperator."),
        )),

        ('fonts', sect.KeyValue(
            ('_monospace',
             SettingValue(types.Font, 'Monospace, "DejaVu Sans Mono", '
                          'Consolas, Monaco, "Bitstream Vera Sans Mono", '
                          '"Andale Mono", "Liberation Mono", "Courier New", '
                          'Courier, monospace, Fixed, Terminal'),
             "Default monospace fonts."),

            ('completion',
             SettingValue(types.Font, "8pt ${_monospace}"),
             "Font used in the completion widget."),

            ('tabbar',
             SettingValue(types.Font, "8pt ${_monospace}"),
             "Font used in the tabbar."),

            ('statusbar',
             SettingValue(types.Font, "8pt ${_monospace}"),
             "Font used in the statusbar."),

        )),
    ])


class SettingValue:

    """Base class for setting values.

    Intended to be subclassed by config value "types".

    Attributes:
        typ: A BaseType subclass.
        default: Default value if the user has not overridden it, as a string.
        value: (property) The currently valid, most important value.
        rawvalue: The current value as a raw string.

    """

    def __init__(self, typ, default):
        """Constructor.

        Args:
            typ: The BaseType to use.
            default: Raw value to set.

        """
        self.typ = typ()
        self.rawvalue = None
        self.default = default

    def __str__(self):
        """Get raw string value."""
        return self.value

    def transformed(self):
        """Get the transformed value."""
        v = self.value
        return self.typ.transform(v)

    @property
    def value(self):
        """Get the currently valid value."""
        return self.rawvalue if self.rawvalue is not None else self.default
