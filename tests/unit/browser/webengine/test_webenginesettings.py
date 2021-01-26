# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import logging

import pytest

QtWebEngineWidgets = pytest.importorskip('PyQt5.QtWebEngineWidgets')

from qutebrowser.browser.webengine import webenginesettings
from qutebrowser.utils import usertypes


@pytest.fixture
def global_settings(monkeypatch, default_profile):
    wrapper = webenginesettings._SettingsWrapper()
    settings = webenginesettings.WebEngineSettings(wrapper)
    settings.init_settings()
    monkeypatch.setattr(webenginesettings, '_global_settings', settings)


@pytest.fixture
def default_profile(monkeypatch):
    """A profile to use which is set as default_profile.

    Note we use a "private" profile here to avoid actually storing data during tests.
    """
    profile = QtWebEngineWidgets.QWebEngineProfile()
    profile.setter = webenginesettings.ProfileSetter(profile)
    monkeypatch.setattr(profile, 'isOffTheRecord', lambda: False)
    monkeypatch.setattr(webenginesettings, 'default_profile', profile)
    return profile


@pytest.fixture
def private_profile(monkeypatch):
    """A profile to use which is set as private_profile."""
    profile = QtWebEngineWidgets.QWebEngineProfile()
    profile.setter = webenginesettings.ProfileSetter(profile)
    monkeypatch.setattr(webenginesettings, 'private_profile', profile)
    return profile


def test_big_cache_size(config_stub, default_profile):
    """Make sure a too big cache size is handled correctly."""
    config_stub.val.content.cache.size = 2 ** 63 - 1
    default_profile.setter.set_http_cache_size()
    assert default_profile.httpCacheMaximumSize() == 2 ** 31 - 1


def test_non_existing_dict(config_stub, monkeypatch, message_mock, caplog,
                           global_settings):
    monkeypatch.setattr(webenginesettings.spell, 'local_filename',
                        lambda _code: None)
    config_stub.val.spellcheck.languages = ['af-ZA']

    with caplog.at_level(logging.WARNING):
        webenginesettings._update_settings('spellcheck.languages')

    msg = message_mock.getmsg(usertypes.MessageLevel.warning)
    expected = ("Language af-ZA is not installed - see scripts/dictcli.py in "
                "qutebrowser's sources")
    assert msg.text == expected


def test_existing_dict(config_stub, monkeypatch, global_settings,
                       default_profile, private_profile):
    monkeypatch.setattr(webenginesettings.spell, 'local_filename',
                        lambda _code: 'en-US-8-0')
    config_stub.val.spellcheck.languages = ['en-US']
    webenginesettings._update_settings('spellcheck.languages')
    for profile in [default_profile, private_profile]:
        assert profile.isSpellCheckEnabled()
        assert profile.spellCheckLanguages() == ['en-US-8-0']


def test_spell_check_disabled(config_stub, monkeypatch, global_settings,
                              default_profile, private_profile):
    config_stub.val.spellcheck.languages = []
    webenginesettings._update_settings('spellcheck.languages')
    for profile in [default_profile, private_profile]:
        assert not profile.isSpellCheckEnabled()


def test_parsed_user_agent(qapp):
    webenginesettings.init_user_agent()
    parsed = webenginesettings.parsed_user_agent
    assert parsed.upstream_browser_key == 'Chrome'
    assert parsed.qt_key == 'QtWebEngine'
