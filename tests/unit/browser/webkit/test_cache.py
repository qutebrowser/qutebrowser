# SPDX-FileCopyrightText: lamarpavel
# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from qutebrowser.qt.core import QUrl, QDateTime
from qutebrowser.qt.network import QNetworkDiskCache, QNetworkCacheMetaData

from qutebrowser.browser.webkit import cache


@pytest.fixture
def disk_cache(tmpdir, config_stub):
    return cache.DiskCache(str(tmpdir))


def build_metadata(url='http://qutebrowser.org/'):
    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    # https://codereview.qt-project.org/c/qt/qtbase/+/465547
    metadata.setRawHeaders([(b"X-Hello", b"World")])

    assert metadata.isValid()
    assert metadata.rawHeaders()
    return metadata


def preload_cache(cache, url='http://www.example.com/', content=b'foobar'):
    metadata = build_metadata(url)
    device = cache.prepare(metadata)
    assert device is not None
    device.write(content)
    cache.insert(device)


def test_cache_config_change_cache_size(config_stub, tmpdir):
    """Change cache size and emit signal to trigger on_config_changed."""
    max_cache_size = 1024
    config_stub.val.content.cache.size = max_cache_size

    disk_cache = cache.DiskCache(str(tmpdir))
    assert disk_cache.maximumCacheSize() == max_cache_size

    config_stub.val.content.cache.size = max_cache_size * 2
    assert disk_cache.maximumCacheSize() == max_cache_size * 2


def test_cache_size_leq_max_cache_size(config_stub, tmpdir):
    """Test cacheSize <= MaximumCacheSize when cache is activated."""
    limit = 100
    config_stub.val.content.cache.size = limit

    disk_cache = cache.DiskCache(str(tmpdir))
    assert disk_cache.maximumCacheSize() == limit

    preload_cache(disk_cache, 'http://www.example.com/')
    preload_cache(disk_cache, 'http://qutebrowser.org')
    preload_cache(disk_cache, 'http://foo.xxx')
    preload_cache(disk_cache, 'http://bar.net')
    assert disk_cache.expire() < limit
    # Add a threshold to the limit due to unforeseeable Qt internals
    assert disk_cache.cacheSize() < limit + 100


def test_cache_existing_metadata_file(tmpdir, disk_cache):
    """Test querying existing meta data file from activated cache."""
    content = b'foobar'
    metadata = build_metadata()

    device = disk_cache.prepare(metadata)
    assert device is not None
    device.write(content)
    disk_cache.insert(device)
    disk_cache.updateMetaData(metadata)

    files = list(tmpdir.visit(fil=lambda path: path.isfile()))
    assert len(files) == 1
    assert disk_cache.fileMetaData(str(files[0])) == metadata


def test_cache_nonexistent_metadata_file(disk_cache):
    """Test querying nonexistent meta data file from activated cache."""
    cache_file = disk_cache.fileMetaData("nosuchfile")
    assert not cache_file.isValid()


def test_cache_get_nonexistent_data(disk_cache):
    """Test querying some data that was never inserted."""
    preload_cache(disk_cache, 'https://qutebrowser.org')

    assert disk_cache.data(QUrl('http://qutebrowser.org')) is None


def test_cache_insert_data(disk_cache):
    """Test if entries inserted into the cache are actually there."""
    url = 'http://qutebrowser.org'
    content = b'foobar'
    assert disk_cache.cacheSize() == 0

    preload_cache(disk_cache, url, content)

    assert disk_cache.cacheSize() != 0
    assert disk_cache.data(QUrl(url)).readAll() == content


def test_cache_remove_data(disk_cache):
    """Test if a previously inserted entry can be removed from the cache."""
    url = 'http://qutebrowser.org'
    preload_cache(disk_cache, url)
    assert disk_cache.cacheSize() > 0

    assert disk_cache.remove(QUrl(url))
    assert disk_cache.cacheSize() == 0


def test_cache_clear_activated(disk_cache):
    """Test if cache is empty after clearing it."""
    assert disk_cache.cacheSize() == 0

    preload_cache(disk_cache)
    assert disk_cache.cacheSize() != 0

    disk_cache.clear()
    assert disk_cache.cacheSize() == 0


def test_cache_metadata(disk_cache):
    """Ensure that DiskCache.metaData() returns exactly what was inserted."""
    url = 'http://qutebrowser.org'
    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    assert metadata.isValid()
    device = disk_cache.prepare(metadata)
    device.write(b'foobar')
    disk_cache.insert(device)

    assert disk_cache.metaData(QUrl(url)) == metadata


def test_cache_update_metadata(disk_cache):
    """Test updating the meta data for an existing cache entry."""
    url = 'http://qutebrowser.org'
    preload_cache(disk_cache, url, b'foo')
    assert disk_cache.cacheSize() > 0

    metadata = QNetworkCacheMetaData()
    metadata.setUrl(QUrl(url))
    assert metadata.isValid()
    disk_cache.updateMetaData(metadata)
    assert disk_cache.metaData(QUrl(url)) == metadata


def test_cache_full(tmpdir):
    """Do a sanity test involving everything."""
    disk_cache = QNetworkDiskCache()
    disk_cache.setCacheDirectory(str(tmpdir))

    url = 'http://qutebrowser.org'
    content = b'cutebowser'
    preload_cache(disk_cache, url, content)
    url2 = 'https://qutebrowser.org'
    content2 = b'ohmycert'
    preload_cache(disk_cache, url2, content2)

    metadata = build_metadata(url)
    soon = QDateTime.currentDateTime().addMonths(4)
    assert soon.isValid()
    metadata.setLastModified(soon)
    assert metadata.isValid()
    disk_cache.updateMetaData(metadata)
    disk_cache.remove(QUrl(url2))

    assert disk_cache.metaData(QUrl(url)).lastModified() == soon
    assert disk_cache.data(QUrl(url)).readAll() == content
