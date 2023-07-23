# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""HTTP network cache."""

from typing import cast
import os.path

from qutebrowser.qt.network import QNetworkDiskCache

from qutebrowser.config import config
from qutebrowser.utils import utils, standarddir


diskcache = cast('DiskCache', None)


class DiskCache(QNetworkDiskCache):

    """Disk cache which sets correct cache dir and size."""

    def __init__(self, cache_dir, parent=None):
        super().__init__(parent)
        self.setCacheDirectory(os.path.join(cache_dir, 'http'))
        self._set_cache_size()
        config.instance.changed.connect(self._set_cache_size)

    def __repr__(self):
        return utils.get_repr(self, size=self.cacheSize(),
                              maxsize=self.maximumCacheSize(),
                              path=self.cacheDirectory())

    @config.change_filter('content.cache.size')
    def _set_cache_size(self):
        """Set the cache size based on the config."""
        size = config.val.content.cache.size
        if size is None:
            size = 1024 * 1024 * 50  # default from QNetworkDiskCachePrivate
        self.setMaximumCacheSize(size)


def init(parent):
    """Initialize the global cache."""
    global diskcache
    diskcache = DiskCache(standarddir.cache(), parent=parent)
