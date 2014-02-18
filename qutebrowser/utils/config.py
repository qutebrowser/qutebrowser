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

"""Configuration storage and config-related utilities.

config         -- The main Config object.
colordict      -- All configured colors.
MONOSPACE      -- A list of suitable monospace fonts.

"""

import os
import io
import os.path
import logging
from configparser import ConfigParser, ExtendedInterpolation

from qutebrowser.utils.misc import read_file

config = None
colordict = {}
fontdict = {}


def init(confdir):
    """Initialize the global objects based on the config in configdir."""
    global config, colordict, fontdict
    config = Config(confdir)
    try:
        colordict = ColorDict(config['colors'])
    except KeyError:
        colordict = ColorDict()
    fontdict = FontDict(config['fonts'])


def get_stylesheet(template):
    """Return a formatted stylesheet based on a template."""
    return template.strip().format(color=colordict, font=fontdict)


class ColorDict(dict):

    """A dict aimed at Qt stylesheet colors."""

    # FIXME we should validate colors in __setitem__ based on:
    # http://qt-project.org/doc/qt-4.8/stylesheet-reference.html#brush
    # http://www.w3.org/TR/CSS21/syndata.html#color-units

    def __getitem__(self, key):
        """Override dict __getitem__.

        If a value wasn't found, return an empty string.
        (Color not defined, so no output in the stylesheet)

        If the key has a .fg. element in it, return  color: X;.
        If the key has a .bg. element in it, return  background-color: X;.

        In all other cases, return the plain value.

        """
        try:
            val = super().__getitem__(key)
        except KeyError:
            return ''
        if 'fg' in key.split('.'):
            return 'color: {};'.format(val)
        elif 'bg' in key.split('.'):
            return 'background-color: {};'.format(val)
        else:
            return val

    def getraw(self, key):
        """Get a value without the transformations done in __getitem__.

        Return a value, or None if the value wasn't found.

        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return None


class FontDict(dict):

    """A dict aimed at Qt stylesheet fonts."""

    def __getitem__(self, key):
        """Override dict __getitem__.

        If a value wasn't found, return an empty string.
        (Color not defined, so no output in the stylesheet)

        In all other cases, return font: <value>.

        """
        try:
            val = super().__getitem__(key)
        except KeyError:
            return ''
        else:
            return 'font: {};'.format(val)

    def getraw(self, key):
        """Get a value without the transformations done in __getitem__.

        Return a value, or None if the value wasn't found.

        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return None


class Config(ConfigParser):

    """Our own ConfigParser subclass."""

    configdir = None
    FNAME = 'config'
    default_cp = None
    config_loaded = False

    def __init__(self, configdir):
        """Config constructor.

        configdir -- directory to store the config in.

        """
        super().__init__(interpolation=ExtendedInterpolation())
        self.default_cp = ConfigParser(interpolation=ExtendedInterpolation())
        self.default_cp.optionxform = lambda opt: opt  # be case-insensitive
        self.default_cp.read_string(read_file('qutebrowser.conf'))
        if not self.configdir:
            return
        self.optionxform = lambda opt: opt  # be case-insensitive
        self.configdir = configdir
        self.configfile = os.path.join(self.configdir, self.FNAME)
        if not os.path.isfile(self.configfile):
            return
        logging.debug("Reading config from {}".format(self.configfile))
        self.read(self.configfile)
        self.config_loaded = True

    def __getitem__(self, key):
        """Get an item from the configparser or default dict.

        Extend ConfigParser's __getitem__.

        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.default_cp[key]

    def get(self, *args, **kwargs):
        """Get an item from the configparser or default dict.

        Extend ConfigParser's get().

        """
        if 'fallback' in kwargs:
            del kwargs['fallback']
        fallback = self.default_cp.get(*args, **kwargs)
        return super().get(*args, fallback=fallback, **kwargs)

    def save(self):
        """Save the config file."""
        if self.configdir is None or not self.config_loaded:
            return
        if not os.path.exists(self.configdir):
            os.makedirs(self.configdir, 0o755)
        logging.debug("Saving config to {}".format(self.configfile))
        with open(self.configfile, 'w') as f:
            self.write(f)
            f.flush()
            os.fsync(f.fileno())

    def dump_userconfig(self):
        """Return the part of the config which was changed by the user."""
        with io.StringIO() as f:
            self.write(f)
            return f.getvalue()
