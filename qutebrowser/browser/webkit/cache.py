# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtNetwork import QNetworkDiskCache, QNetworkCacheMetaData

from qutebrowser.config import config
from qutebrowser.utils import utils, objreg, qtutils


class DiskCache(QNetworkDiskCache):

    """Disk cache which sets correct cache dir and size.

    Attributes:
        _activated: Whether the cache should be used.
        _cache_dir: The base directory for cache files (standarddir.cache())
    """

    def __init__(self, cache_dir, parent=None):
        super().__init__(parent)
        self._cache_dir = cache_dir
        self._maybe_activate()
        objreg.get('config').changed.connect(self.on_config_changed)

    def __repr__(self):
        return utils.get_repr(self, size=self.cacheSize(),
                              maxsize=self.maximumCacheSize(),
                              path=self.cacheDirectory())

    def _set_cache_size(self):
        """Set the cache size based on the config."""
        size = config.get('storage', 'cache-size')
        if size is None:
            size = 1024 * 1024 * 50  # default from QNetworkDiskCachePrivate
        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-59909
        if (qtutils.version_check('5.7.1') and
                not qtutils.version_check('5.9')):  # pragma: no cover
            size = 0
        self.setMaximumCacheSize(size)

    def _maybe_activate(self):
        """Activate/deactivate the cache based on the config."""
        if config.get('general', 'private-browsing'):
            self._activated = False
        else:
            self._activated = True
            self.setCacheDirectory(os.path.join(self._cache_dir, 'http'))
            self._set_cache_size()

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update cache size/activated if the config was changed."""
        if (section, option) == ('storage', 'cache-size'):
            self._set_cache_size()
        elif (section, option) == ('general',  # pragma: no branch
                                   'private-browsing'):
            self._maybe_activate()

    def cacheSize(self):
        """Return the current size taken up by the cache.

        Return:
            An int.
        """
        if self._activated:
            return super().cacheSize()
        else:
            return 0

    def fileMetaData(self, filename):
        """Return the QNetworkCacheMetaData for the cache file filename.

        Args:
            filename: The file name as a string.

        Return:
            A QNetworkCacheMetaData object.
        """
        if self._activated:
            return super().fileMetaData(filename)
        else:
            return QNetworkCacheMetaData()

    def data(self, url):
        """Return the data associated with url.

        Args:
            url: A QUrl.

        return:
            A QIODevice or None.
        """
        if self._activated:
            return super().data(url)
        else:
            return None

    def insert(self, device):
        """Insert the data in device and the prepared meta data into the cache.

        Args:
            device: A QIODevice.
        """
        if self._activated:
            super().insert(device)
        else:
            return None

    def metaData(self, url):
        """Return the meta data for the url url.

        Args:
            url: A QUrl.

        Return:
            A QNetworkCacheMetaData object.
        """
        if self._activated:
            return super().metaData(url)
        else:
            return QNetworkCacheMetaData()

    def prepare(self, meta_data):
        """Return the device that should be populated with the data.

        Args:
            meta_data: A QNetworkCacheMetaData object.

        Return:
            A QIODevice or None.
        """
        if self._activated:
            return super().prepare(meta_data)
        else:
            return None

    def remove(self, url):
        """Remove the cache entry for url.

        Return:
            True on success, False otherwise.
        """
        if self._activated:
            return super().remove(url)
        else:
            return False

    def updateMetaData(self, meta_data):
        """Update the cache meta date for the meta_data's url to meta_data.

        Args:
            meta_data: A QNetworkCacheMetaData object.
        """
        if self._activated:
            super().updateMetaData(meta_data)
        else:
            return

    def clear(self):
        """Remove all items from the cache."""
        if self._activated:
            super().clear()
        else:
            return
