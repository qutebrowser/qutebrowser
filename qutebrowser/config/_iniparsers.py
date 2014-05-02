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

"""Parsers for INI-like config files, based on Python's ConfigParser."""

import os
import os.path
import logging
from configparser import ConfigParser


class ReadConfigParser(ConfigParser):

    """Our own ConfigParser subclass to read the main config.

    Attributes:
        _configdir: The directory to read the config from.
        _configfile: The config file path.
    """

    def __init__(self, configdir, fname):
        """Config constructor.

        Args:
            configdir: Directory to read the config from.
            fname: Filename of the config file.
        """
        super().__init__(interpolation=None, comment_prefixes='#')
        self.optionxform = lambda opt: opt  # be case-insensitive
        self._configdir = configdir
        self._configfile = os.path.join(self._configdir, fname)
        if not os.path.isfile(self._configfile):
            return
        logging.debug("Reading config from {}".format(self._configfile))
        self.read(self._configfile, encoding='utf-8')


class ReadWriteConfigParser(ReadConfigParser):

    """ConfigParser subclass used for auxillary config files."""

    def save(self):
        """Save the config file."""
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        logging.debug("Saving config to {}".format(self._configfile))
        with open(self._configfile, 'w', encoding='utf-8') as f:
            self.write(f)
