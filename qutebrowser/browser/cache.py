# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from PyQt5.QtNetwork import QNetworkDiskCache, QNetworkCacheMetaData

from qutebrowser.config import config
from qutebrowser.utils import utils, standarddir, objreg


class DiskCache(QNetworkDiskCache):

    """Disk cache which sets correct cache dir and size."""

    def __init__(self, parent=None):
        super().__init__(parent)
        cache_dir = standarddir.get(QStandardPaths.CacheLocation)
        self.setCacheDirectory(os.path.join(cache_dir, 'http'))
        self.setMaximumCacheSize(config.get('storage', 'cache-size'))
        objreg.get('config').changed.connect(self.cache_size_changed)

    def __repr__(self):
        return utils.get_repr(self, size=self.cacheSize(),
                              maxsize=self.maximumCacheSize(),
                              path=self.cacheDirectory())

    @config.change_filter('storage', 'cache-size')
    def cache_size_changed(self):
        """Update cache size if the config was changed."""
        self.setMaximumCacheSize(config.get('storage', 'cache-size'))

    def cacheSize(self):
        """Return the current size taken up by the cache.

        Return:
            An int.
        """
        if objreg.get('general', 'private-browsing'):
            return 0
        else:
            return super().cacheSize()

    def fileMetaData(self, filename):
        """Returns the QNetworkCacheMetaData for the cache file filename.

        Args:
            filename: The file name as a string.

        Return:
            A QNetworkCacheMetaData object.
        """
        if objreg.get('general', 'private-browsing'):
            return QNetworkCacheMetaData()
        else:
            return super().fileMetaData(filename)

    def data(self, url):
        """Return the data associated with url.

        Args:
            url: A QUrl.

        return:
            A QIODevice or None.
        """
        if objreg.get('general', 'private-browsing'):
            return None
        else:
            return super().data(url)

    def insert(self, device):
        """Insert the data in device and the prepared meta data into the cache.

        Args:
            device: A QIODevice.
        """
        if objreg.get('general', 'private-browsing'):
            return
        else:
            super().insert(device)

    def metaData(self, url):
        """Return the meta data for the url url.

        Args:
            url: A QUrl.

        Return:
            A QNetworkCacheMetaData object.
        """
        if objreg.get('general', 'private-browsing'):
            return QNetworkCacheMetaData()
        else:
            return super().metaData(url)

    def prepare(self, meta_data):
        """Return the device that should be populated with the data.

        Args:
            meta_data: A QNetworkCacheMetaData object.

        Return:
            A QIODevice or None.
        """
        if objreg.get('general', 'private-browsing'):
            return None
        else:
            return super().prepare(meta_data)

    def remove(self, url):
        """Remove the cache entry for url.

        Return:
            True on success, False otherwise.
        """
        if objreg.get('general', 'private-browsing'):
            return False
        else:
            return super().remove(url)

    def updateMetaData(self, meta_data):
        """Updates the cache meta date for the meta_data's url to meta_data.

        Args:
            meta_data: A QNetworkCacheMetaData object.
        """
        if objreg.get('general', 'private-browsing'):
            return
        else:
            super().updateMetaData(meta_data)

    def clear(self):
        """Removes all items from the cache."""
        if objreg.get('general', 'private-browsing'):
            return
        else:
            super().clear()
