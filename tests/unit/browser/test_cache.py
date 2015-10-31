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

from PyQt5.QtCore import QUrl, QDateTime, QDataStream
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
    limit = 100
    config_stub.data = {
        'storage': {'cache-size': limit},
        'general': {'private-browsing': False}
    }
    disk_cache = cache.DiskCache(str(tmpdir))
    assert disk_cache.maximumCacheSize() == limit

    preload_cache(disk_cache, 'http://www.example.com/')
    preload_cache(disk_cache, 'http://qutebrowser.org')
    preload_cache(disk_cache, 'http://foo.xxx')
    preload_cache(disk_cache, 'http://bar.net')
    assert disk_cache.expire() < limit
    # Add a threshold to the limit due to unforseeable Qt internals
    assert disk_cache.cacheSize() < limit+100


def test_cache_size_deactivated(config_stub, tmpdir):
    """Confirm that the cache size returns 0 when deactivated."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': True}
    }
    disk_cache = cache.DiskCache(str(tmpdir))
    assert disk_cache.cacheSize() == 0


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


def test_cache_deactivated_get_data(config_stub, tmpdir):
    """Query some data from a deactivated cache."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': True}
    }
    disk_cache = cache.DiskCache(str(tmpdir))

    url = QUrl('http://www.example.com/')
    assert disk_cache.data(url) is None


def test_cache_get_nonexistent_data(config_stub, tmpdir):
    """Test querying some data that was never inserted."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': False}
    }
    disk_cache = cache.DiskCache(str(tmpdir))
    preload_cache(disk_cache, 'https://qutebrowser.org')

    assert disk_cache.data(QUrl('http://qutebrowser.org')) is None


def test_cache_deactivated_remove_data(config_stub, tmpdir):
    """Test removing some data from a deactivated cache."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': True}
    }
    disk_cache = cache.DiskCache(str(tmpdir))

    url = QUrl('http://www.example.com/')
    assert disk_cache.remove(url) == False


def test_cache_insert_data(tmpdir):
    """Test if entries inserted into the cache are actually there."""
    url = 'http://qutebrowser.org'
    content = b'foobar'
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    assert disk_cache.cacheSize() == 0

    preload_cache(disk_cache, url, content)

    assert disk_cache.cacheSize() != 0
    assert disk_cache.data(QUrl(url)).readAll() == content


def test_cache_deactivated_insert_data(config_stub, tmpdir):
    """Insert data when cache is deactivated."""
    # First create an activated cache to get a valid QIODevice from it
    url = 'http://qutebrowser.org'
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    device = disk_cache.prepare(metadata)
    assert device is not None

    # Now create the deactivated cache and insert the valid device created
    # above (there probably is a better way to get a valid QIODevice...)
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': True}
    }

    deactivated_cache = QNetworkDiskCache()
    deactivated_cache.setCacheDirectory(str(tmpdir))
    assert disk_cache.insert(device) is None



def test_cache_remove_data(tmpdir):
    """Test if a previously inserted entry can be removed from the cache."""
    url = 'http://qutebrowser.org'
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    preload_cache(disk_cache, url)
    assert disk_cache.cacheSize() > 0

    assert disk_cache.remove(QUrl(url)) == True
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
    url = 'http://qutebrowser.org'
    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    assert metadata.isValid()
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    device = disk_cache.prepare(metadata)
    device.write(b'foobar')
    disk_cache.insert(device)

    assert disk_cache.metaData(QUrl(url)) == metadata


def test_cache_update_metadata(tmpdir):
    """Test updating the meta data for an existing cache entry."""
    url = 'http://qutebrowser.org'
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))
    preload_cache(disk_cache, url, b'foo')
    assert disk_cache.cacheSize() > 0

    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    assert metadata.isValid()
    disk_cache.updateMetaData(metadata)
    assert disk_cache.metaData(QUrl(url)) == metadata


def test_cache_deactivated_update_metadata(config_stub, tmpdir):
    """Test updating the meta data when cache is not activated."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': True}
    }
    url = 'http://qutebrowser.org'
    disk_cache = cache.DiskCache(str(tmpdir))

    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    assert metadata.isValid()
    assert disk_cache.updateMetaData(metadata) is None


def test_cache_full(config_stub, tmpdir):
    """Do a sanity test involving everything."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': False}
    }
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))

    url = 'http://qutebrowser.org'
    content = b'cutebowser'
    preload_cache(disk_cache, url, content)
    url2 = 'https://qutebrowser.org'
    content2 = b'ohmycert'
    preload_cache(disk_cache, url2, content2)

    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    soon = QDateTime.currentDateTime().addMonths(4)
    assert soon.isValid()
    metadata.setLastModified(soon)
    assert metadata.isValid()
    disk_cache.updateMetaData(metadata)
    disk_cache.remove(QUrl(url2))

    assert disk_cache.metaData(QUrl(url)).lastModified() == soon
    assert disk_cache.data(QUrl(url)).readAll() == content
