# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 lamarpavel
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

"""Tests for qutebrowser.browser.cache"""

from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QNetworkDiskCache, QNetworkCacheMetaData

from qutebrowser.browser import cache


def preload_cache(cache, url='http://www.example.com/', content=b'foobar'):
    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    assert metadata.isValid()
    device = cache.prepare(metadata)
    assert device is not None
    device.write(content)
    cache.insert(device)


def test_cache_size_leq_max_cache_size(config_stub, tmpdir):
    """Test cacheSize <= MaximumCacheSize when cache is activated."""
    LIMIT = 100
    config_stub.data = {
        'storage': {'cache-size': LIMIT},
        'general': {'private-browsing': False}
    }
    disk_cache = cache.DiskCache(str(tmpdir))
    assert disk_cache.maximumCacheSize() == LIMIT

    preload_cache(disk_cache, 'http://www.example.com/')
    preload_cache(disk_cache, 'http://qutebrowser.org')
    preload_cache(disk_cache, 'http://foo.xxx')
    preload_cache(disk_cache, 'http://bar.net')
    assert disk_cache.expire() < LIMIT
    assert disk_cache.cacheSize() <= LIMIT


def test_cache_deactivated_private_browsing(config_stub, tmpdir):
    """Test if cache is deactivated in private-browsing mode."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': True}
    }
    disk_cache = cache.DiskCache(str(tmpdir))

    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl('http://www.example.com/'))
    assert metadata.isValid()
    assert disk_cache.prepare(metadata) is None


def test_cache_insert_data(tmpdir):
    """Test if entries inserted into the cache are actually there."""
    URL = 'http://qutebrowser.org'
    CONTENT = b'foobar'
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    assert disk_cache.cacheSize() == 0

    preload_cache(disk_cache, URL, CONTENT)

    assert disk_cache.cacheSize() != 0
    assert disk_cache.data(QUrl(URL)).readAll() == CONTENT


def test_cache_remove_data(tmpdir):
    """Test if a previously inserted entry can be removed from the cache."""
    URL = 'http://qutebrowser.org'
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    preload_cache(disk_cache, URL)
    assert disk_cache.cacheSize() > 0

    assert disk_cache.remove(QUrl(URL))
    assert disk_cache.cacheSize() == 0


def test_cache_clear_activated(config_stub, tmpdir):
    """Test if cache is empty after clearing it."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': False}
    }
    disk_cache = cache.DiskCache(str(tmpdir))
    assert disk_cache.cacheSize() == 0

    preload_cache(disk_cache)
    assert disk_cache.cacheSize() != 0

    disk_cache.clear()
    assert disk_cache.cacheSize() == 0


def test_cache_metadata(tmpdir):
    """Ensure that DiskCache.metaData() returns exactly what was inserted."""
    URL = 'http://qutebrowser.org'
    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(URL))
    assert metadata.isValid()
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    device = disk_cache.prepare(metadata)
    device.write(b'foobar')
    disk_cache.insert(device)

    assert disk_cache.metaData(QUrl(URL)) == metadata


def test_cache_update_metadata(tmpdir):
    """Test updating the meta data for an existing cache entry."""
    URL = 'http://qutebrowser.org'
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    preload_cache(disk_cache, URL, b'foo')
    assert disk_cache.cacheSize() > 0

    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(URL))
    assert metadata.isValid()
    disk_cache.updateMetaData(metadata)
    assert disk_cache.metaData(QUrl(URL)) == metadata
