# SPDX-FileCopyrightText: Jay Kamat <jaygkamat@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
            config.cache['tabs.padding']
            config.cache['tabs.indicator.width']
            config.cache['tabs.indicator.padding']
            config.cache['tabs.min_width']
            config.cache['tabs.max_width']
            config.cache['tabs.pinned.shrink']
    benchmark(_run_bench)
