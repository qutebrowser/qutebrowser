# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import typing
import os.path

from PyQt5.QtNetwork import QNetworkDiskCache

from qutebrowser.config import config
from qutebrowser.utils import utils, qtutils, standarddir


diskcache = typing.cast('DiskCache', None)


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
        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-59909
        if not qtutils.version_check('5.9', compiled=False):
            size = 0  # pragma: no cover
        self.setMaximumCacheSize(size)


def init(parent):
    """Initialize the global cache."""
    global diskcache
    diskcache = DiskCache(standarddir.cache(), parent=parent)
