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

"""Parser for line-based configurations like histories."""

import os
import os.path
import logging
from PyQt5.QtCore import pyqtSlot


class LineConfigParser:

    """Parser for configuration files which are simply line-based.

    Attributes:
        data: A list of lines.
        _configdir: The directory to read the config from.
        _configfile: The config file path.
    """

    def __init__(self, configdir, fname, limit=None):
        """Config constructor.

        Args:
            configdir: Directory to read the config from.
            fname: Filename of the config file.
            limit: Config tuple (section, option) which contains a limit.
        """
        self._configdir = configdir
        self._configfile = os.path.join(self._configdir, fname)
        self._limit = limit
        self.data = None
        if not os.path.isfile(self._configfile):
            return
        logging.debug("Reading config from {}".format(self._configfile))
        self.read(self._configfile)

    def read(self, filename):
        """Read the data from a file."""
        with open(filename, 'r') as f:
            self.data = [line.rstrip('\n') for line in f.readlines()]

    def write(self, fp, limit=-1):
        """Write the data to a file.

        Arguments:
            fp: A file object to write the data to.
            limit: How many lines to write, or -1 for no limit.
        """
        if limit == -1:
            data = self.data
        else:
            data = self.data[-limit:]
        fp.write('\n'.join(data))

    def save(self):
        """Save the config file."""
        if self.data is None:
            return
        import qutebrowser.config.config as config
        limit = -1 if self._limit is None else config.config.get(*self._limit)
        if limit == 0:
            return
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        logging.debug("Saving config to {}".format(self._configfile))
        with open(self._configfile, 'w') as f:
            self.write(f, limit)

    @pyqtSlot(str, str, object)
    def on_config_changed(self, section, option, value):
        """Delete the file if the limit was changed to 0."""
        if self._limit is None:
            return
        if (section, option) == self._limit and value == 0:
            if os.path.exists(self._configfile):
                os.remove(self._configfile)
