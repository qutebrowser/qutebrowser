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

"""Configuration storage and config-related utilities."""

import os
import io
import os.path
import logging
import textwrap
from collections import OrderedDict
from configparser import (ConfigParser, ExtendedInterpolation, NoSectionError,
                          NoOptionError)

#from qutebrowser.utils.misc import read_file
import qutebrowser.config.conftypes as types
import qutebrowser.config.sections as sect
from qutebrowser.config.templates import SettingValue

config = None
state = None

# Special value for an unset fallback, so None can be passed as fallback.
_UNSET = object()


def init(confdir):
    """Initialize the global objects based on the config in configdir.

    Args:
        confdir: The directory where the configs are stored in.

    """
    global config, state
    logging.debug("Config init, confdir {}".format(confdir))
    #config = Config(confdir, 'qutebrowser.conf',
    #                read_file('qutebrowser.conf'))
    config = NewConfig()
    state = Config(confdir, 'state', always_save=True)


class NewConfig:

    """Contains the structure of the config file."""

    _FIRST_COMMENT = (
        'vim: ft=dosini\n\n'
        'Configfile for qutebrowser.\n\n'
        "This configfile is parsed by python's configparser in extended "
        'interpolation mode. The format is very INI-like, so there are '
        'categories like [general] with "key = value"-pairs.\n\n'
        "Note that you shouldn't add your own comments, as this file is "
        'regenerated every time the config is saved.\n\n'
        'Interpolation looks like  ${value}  or  ${section:value} and will be '
        'replaced by the respective value.\n\n'
        'This is the default config, so if you want to remove anything from '
        'here (as opposed to change/add), for example a keybinding, set it to '
        'an empty value.')

    _SECTION_DESC = {
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

    def __init__(self):
        MONOSPACE = ('Monospace, "DejaVu Sans Mono", Consolas, Monaco, '
                     '"Bitstream Vera Sans Mono", "Andale Mono", '
                     '"Liberation Mono", "Courier New", Courier, monospace, '
                     'Fixed, Terminal')

        self.config = OrderedDict([
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
                 "Whether to wrap search to the top when arriving at the "
                 "end."),

                ('startpage',
                 SettingValue(types.List, "http://www.duckduckgo.com"),
                 "The default page(s) to open at the start, separated with "
                 "commas."),

                ('auto_search',
                 SettingValue(types.AutoSearch, "naive"),
                 "Whether to start a search when something else than an URL "
                 "is entered."),

                ('zoomlevels',
                 SettingValue(types.Int, "25,33,50,67,75,90,100,110,125,150,"
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
                 "Whether there should be scroll buttons if there are too "
                 "many tabs."),

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
                 "Background color of the completion widget category "
                 "headers."),

                ('completion.category.border.top',
                 SettingValue(types.Color, "#808080"),
                 "Top border color of the completion widget category "
                 "headers."),

                ('completion.category.border.bottom',
                 SettingValue(types.Color, "#bbbbbb"),
                 "Bottom border color of the completion widget category "
                 "headers."),

                ('completion.item.selected.fg',
                 SettingValue(types.Color, "#333333"),
                 "Foreground color of the selected completion item."),

                ('completion.item.selected.bg',
                 SettingValue(types.Color, "#ffec8b"),
                 "Background color of the selected completion item."),

                ('completion.item.selected.border.top',
                 SettingValue(types.Color, "#f2f2c0"),
                 "Top border color of the completion widget category "
                 "headers."),

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
                 SettingValue(types.Color, "white", "${statusbar.fg}"),
                 "Foreground color of the statusbar if there was an error."),

                ('statusbar.progress.bg',
                 SettingValue(types.Color, "white"),
                 "Background color of the progress bar."),

                ('statusbar.url.fg',
                 SettingValue(types.Color, "white", "${statusbar.fg}"),
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
                 SettingValue(types.Font, MONOSPACE),
                 "Default monospace fonts."),

                ('completion',
                 SettingValue(types.Font, "8pt " + MONOSPACE,
                              "8pt ${_monospace}"),
                 "Font used in the completion widget."),

                ('tabbar',
                 SettingValue(types.Font, "8pt " + MONOSPACE,
                              "8pt ${_monospace}"),
                 "Font used in the tabbar."),

                ('statusbar',
                 SettingValue(types.Font, "8pt " + MONOSPACE,
                              "8pt ${_monospace}"),
                 "Font used in the statusbar."),

            )),
        ])

    def __getitem__(self, key):
        """Get a section from the config."""
        return self.config[key]

    def __str__(self):
        """Get the whole config as a string."""
        # FIXME empty lines get discared
        # FIXME we should set subsequent_indent for config options later
        wrapper = textwrap.TextWrapper(
            width=72, replace_whitespace=False, break_long_words=False,
            break_on_hyphens=False, initial_indent='# ',
            subsequent_indent='# ')
        lines = []
        for par in map(wrapper.wrap, self._FIRST_COMMENT.splitlines()):
            lines += par
        for secname, section in self.config.items():
            lines.append('\n[{}]'.format(secname))
            for par in map(wrapper.wrap,
                           self._SECTION_DESC[secname].splitlines()):
                lines += par
            for optname, option in section.items():
                # FIXME display option comment
                lines.append('{} = {}'.format(optname, option))
        return '\n'.join(lines)

    def get(self, section, option, fallback=_UNSET):
        """Get the real (transformed) value from a section/option."""
        try:
            val = self.config[section][option]
        except KeyError:
            if fallback is _UNSET:
                raise
            else:
                return fallback
        else:
            return val.value

    def save(self):
        """Save the config file."""
        # FIXME to be implemented
        pass

    def dump_userconfig(self):
        """Get the part of the config which was changed by the user.

        Return:
            The changed config part as string.

        """
        # FIXME to be implemented
        pass


class Config(ConfigParser):

    """Our own ConfigParser subclass.

    Attributes:
        _configdir: The dictionary to save the config in.
        _default_cp: The ConfigParser instance supplying the default values.
        _config_loaded: Whether the config was loaded successfully.

    """

    def __init__(self, configdir, fname, default_config=None,
                 always_save=False):
        """Config constructor.

        Args:
            configdir: Directory to store the config in.
            fname: Filename of the config file.
            default_config: Default config as string.
            always_save: Whether to always save the config, even when it wasn't
                         loaded.

        """
        super().__init__(interpolation=ExtendedInterpolation())
        self._config_loaded = False
        self.always_save = always_save
        self._configdir = configdir
        self._default_cp = ConfigParser(interpolation=ExtendedInterpolation())
        self._default_cp.optionxform = lambda opt: opt  # be case-insensitive
        if default_config is not None:
            self._default_cp.read_string(default_config)
        if not self._configdir:
            return
        self.optionxform = lambda opt: opt  # be case-insensitive
        self._configdir = configdir
        self.configfile = os.path.join(self._configdir, fname)
        if not os.path.isfile(self.configfile):
            return
        logging.debug("Reading config from {}".format(self.configfile))
        self.read(self.configfile)
        self._config_loaded = True

    def __getitem__(self, key):
        """Get an item from the configparser or default dict.

        Extend ConfigParser's __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            The value of the main or fallback ConfigParser.

        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return self._default_cp[key]

    def get(self, *args, raw=False, vars=None, fallback=_UNSET):
        """Get an item from the configparser or default dict.

        Extend ConfigParser's get().

        This is a bit of a hack, but it (hopefully) works like this:
            - Get value from original configparser.
            - If that's not available, try the default_cp configparser
            - If that's not available, try the fallback given as kwarg
            - If that's not available, we're doomed.

        Args:
            *args: Passed to the other configparsers.
            raw: Passed to the other configparsers (do not interpolate).
            var: Passed to the other configparsers.
            fallback: Fallback value if value wasn't found in any configparser.

        Raise:
            configparser.NoSectionError/configparser.NoOptionError if the
            default configparser raised them and there is no fallback.

        """
        # pylint: disable=redefined-builtin
        # The arguments returned by the ConfigParsers actually are strings
        # already, but we add an explicit str() here to trick pylint into
        # thinking a string is returned (rather than an object) to avoid
        # maybe-no-member errors.
        try:
            return str(super().get(*args, raw=raw, vars=vars))
        except (NoSectionError, NoOptionError):
            pass
        try:
            return str(self._default_cp.get(*args, raw=raw, vars=vars))
        except (NoSectionError, NoOptionError):
            if fallback is _UNSET:
                raise
            else:
                return fallback

    def save(self):
        """Save the config file."""
        if self._configdir is None or (not self._config_loaded and
                                       not self.always_save):
            logging.warning("Not saving config (dir {}, config {})".format(
                self._configdir, 'loaded' if self._config_loaded
                else 'not loaded'))
            return
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        logging.debug("Saving config to {}".format(self.configfile))
        with open(self.configfile, 'w') as f:
            self.write(f)
            f.flush()
            os.fsync(f.fileno())

    def dump_userconfig(self):
        """Get the part of the config which was changed by the user.

        Return:
            The changed config part as string.

        """
        with io.StringIO() as f:
            self.write(f)
            return f.getvalue()
