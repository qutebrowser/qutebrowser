# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""HTTP network cache."""

import os.path

from PyQt5.QtCore import QStandardPaths
from PyQt5.QtNetwork import QNetworkDiskCache

from qutebrowser.config import config
from qutebrowser.utils import utils


class DiskCache(QNetworkDiskCache):

    """Disk cache which sets correct cache dir and size."""

    def __init__(self, parent=None):
        super().__init__(parent)
        cache_dir = utils.get_standard_dir(QStandardPaths.CacheLocation)
        self.setCacheDirectory(os.path.join(cache_dir, 'http'))
        self.setMaximumCacheSize(config.get('storage', 'cache-size'))

    def __repr__(self):
        return '<{} size={}, maxsize={}, path={}>'.format(
            self.__class__.__name__, self.cacheSize(), self.maximumCacheSize(),
            self.cacheDirectory())
