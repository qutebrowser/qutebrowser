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

from unittest import mock

from qutebrowser.browser import cache
from qutebrowser.utils import objreg


def test_cache_size_leq_max_cache_size(config_stub, tmpdir):
    """Test cacheSize <= MaximumCacheSize when cache is activated."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': False}
    }
    disk_cache = cache.DiskCache(str(tmpdir))
    assert(disk_cache.cacheSize() <= 1024)


def test_cache_deactivated_private_browsing(config_stub, tmpdir):
    """Test if cache is deactivated in private-browsing mode."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': True}
    }
    disk_cache = cache.DiskCache(str(tmpdir))
    assert(disk_cache.cacheSize() == 0)


def test_cache_deactivated_no_cachedir(config_stub):
    """Test if cache is deactivated when there is no cache-dir."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': False}
    }
    disk_cache = cache.DiskCache("")
    assert(disk_cache.cacheSize() == 0)


def test_clear_cache_activated(config_stub, tmpdir):
    """Test if cache is empty after clearing it."""
    config_stub.data = {
        'storage': {'cache-size': 1024},
        'general': {'private-browsing': False}
    }
    disk_cache = cache.DiskCache(str(tmpdir))
    disk_cache.clear()
    assert(disk_cache.cacheSize() == 0)
