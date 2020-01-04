# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import types
import logging

import pytest

pytest.importorskip('PyQt5.QtWebEngineWidgets')

from qutebrowser.browser.webengine import webenginesettings
from qutebrowser.utils import usertypes, qtutils
from qutebrowser.misc import objects


@pytest.fixture(autouse=True)
def init(qapp, config_stub, cache_tmpdir, data_tmpdir, monkeypatch):
    monkeypatch.setattr(webenginesettings.webenginequtescheme, 'init',
                        lambda: None)
    monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)
    init_args = types.SimpleNamespace(enable_webengine_inspector=False)
    webenginesettings.init(init_args)
    config_stub.changed.disconnect(webenginesettings._update_settings)


def test_big_cache_size(config_stub):
    """Make sure a too big cache size is handled correctly."""
    config_stub.val.content.cache.size = 2 ** 63 - 1
    profile = webenginesettings.default_profile
    profile.setter.set_http_cache_size()
    assert profile.httpCacheMaximumSize() == 2 ** 31 - 1


@pytest.mark.skipif(
    not qtutils.version_check('5.8'), reason="Needs Qt 5.8 or newer")
def test_non_existing_dict(config_stub, monkeypatch, message_mock, caplog):
    monkeypatch.setattr(webenginesettings.spell, 'local_filename',
                        lambda _code: None)
    config_stub.val.spellcheck.languages = ['af-ZA']

    with caplog.at_level(logging.WARNING):
        webenginesettings._update_settings('spellcheck.languages')

    msg = message_mock.getmsg(usertypes.MessageLevel.warning)
    expected = ("Language af-ZA is not installed - see scripts/dictcli.py in "
                "qutebrowser's sources")
    assert msg.text == expected


@pytest.mark.skipif(
    not qtutils.version_check('5.8'), reason="Needs Qt 5.8 or newer")
def test_existing_dict(config_stub, monkeypatch):
    monkeypatch.setattr(webenginesettings.spell, 'local_filename',
                        lambda _code: 'en-US-8-0')
    config_stub.val.spellcheck.languages = ['en-US']
    webenginesettings._update_settings('spellcheck.languages')
    for profile in [webenginesettings.default_profile,
                    webenginesettings.private_profile]:
        assert profile.isSpellCheckEnabled()
        assert profile.spellCheckLanguages() == ['en-US-8-0']


@pytest.mark.skipif(
    not qtutils.version_check('5.8'), reason="Needs Qt 5.8 or newer")
def test_spell_check_disabled(config_stub, monkeypatch):
    config_stub.val.spellcheck.languages = []
    webenginesettings._update_settings('spellcheck.languages')
    for profile in [webenginesettings.default_profile,
                    webenginesettings.private_profile]:
        assert not profile.isSpellCheckEnabled()


def test_default_user_agent_saved():
    assert webenginesettings.parsed_user_agent is not None


def test_parsed_user_agent(qapp):
    webenginesettings.init_user_agent()
    parsed = webenginesettings.parsed_user_agent
    assert parsed.upstream_browser_key == 'Chrome'
    assert parsed.qt_key == 'QtWebEngine'
