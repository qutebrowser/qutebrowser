# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Jay Kamat <jaygkamat@gmail.com>
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

# False-positives
# FIXME: Report this to pylint?
# pylint: disable=unsubscriptable-object,useless-suppression

"""Tests for qutebrowser.config.configcache."""

import pytest

from qutebrowser.config import config


def test_configcache_except_pattern(config_stub):
    with pytest.raises(AssertionError):
        assert config.cache['content.javascript.enabled']


def test_configcache_error_set(config_stub):
    # pylint: disable=unsupported-assignment-operation,useless-suppression
    with pytest.raises(TypeError):
        config.cache['content.javascript.enabled'] = True


def test_configcache_get(config_stub):
    assert len(config.cache._cache) == 0
    assert not config.cache['auto_save.session']
    assert len(config.cache._cache) == 1
    assert not config.cache['auto_save.session']


def test_configcache_get_after_set(config_stub):
    assert not config.cache['auto_save.session']
    config_stub.val.auto_save.session = True
    assert config.cache['auto_save.session']


def test_configcache_naive_benchmark(config_stub, benchmark):
    def _run_bench():
        for _i in range(10000):
            # pylint: disable=pointless-statement
            config.cache['tabs.padding']
            config.cache['tabs.indicator.width']
            config.cache['tabs.indicator.padding']
            config.cache['tabs.min_width']
            config.cache['tabs.max_width']
            config.cache['tabs.pinned.shrink']
            # pylint: enable=pointless-statement
    benchmark(_run_bench)
