# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

import pytest

QtWebEngineCore = pytest.importorskip('qutebrowser.qt.webenginecore')
QWebEngineProfile = QtWebEngineCore.QWebEngineProfile
QWebEngineSettings = QtWebEngineCore.QWebEngineSettings

from qutebrowser.browser.webengine import webenginesettings
from qutebrowser.utils import usertypes
from qutebrowser.config import configdata


@pytest.fixture
def settings(default_profile):
    wrapper = webenginesettings._SettingsWrapper()
    return webenginesettings.WebEngineSettings(wrapper)


@pytest.fixture
def global_settings(monkeypatch, settings):
    settings.init_settings()
    monkeypatch.setattr(webenginesettings, '_global_settings', settings)


@pytest.fixture
def default_profile(monkeypatch):
    """A profile to use which is set as default_profile.

    Note we use a "private" profile here to avoid actually storing data during tests.
    """
    profile = QtWebEngineCore.QWebEngineProfile()
    profile.setter = webenginesettings.ProfileSetter(profile)
    monkeypatch.setattr(profile, 'isOffTheRecord', lambda: False)
    monkeypatch.setattr(webenginesettings, 'default_profile', profile)
    return profile


@pytest.fixture
def private_profile(monkeypatch):
    """A profile to use which is set as private_profile."""
    profile = QtWebEngineCore.QWebEngineProfile()
    profile.setter = webenginesettings.ProfileSetter(profile)
    monkeypatch.setattr(webenginesettings, 'private_profile', profile)
    return profile


@pytest.mark.parametrize("setting, value, getter, expected", [
    # attribute
    (
        "content.images", False,
        lambda settings:
            settings.testAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages),
        False,
    ),
    # font size
    (
        "fonts.web.size.default", 23,
        lambda settings:
            settings.fontSize(QWebEngineSettings.FontSize.DefaultFontSize),
        23,
    ),
    # font family
    (
        "fonts.web.family.standard", "Comic Sans MS",
        lambda settings:
            settings.fontFamily(QWebEngineSettings.FontFamily.StandardFont),
        "Comic Sans MS",
    ),
    # encoding
    (
        "content.default_encoding", "utf-16",
        lambda settings: settings.defaultTextEncoding(),
        "utf-16",
    ),
    # unknown URL scheme policy
    (
        "content.unknown_url_scheme_policy", "allow-all",
        lambda settings: settings.unknownUrlSchemePolicy(),
        QWebEngineSettings.UnknownUrlSchemePolicy.AllowAllUnknownUrlSchemes,
    ),
    # JS clipboard
    (
        "content.javascript.clipboard", "access",
        lambda settings: settings.testAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard),
        True,
    ),
])
def test_initial_settings(settings, config_stub, default_profile,
                          setting, value, getter, expected):
    """Make sure initial setting values are applied correctly."""
    qt_settings = default_profile.settings()
    initial = getter(qt_settings)
    assert initial != expected  # no point in testing for the Qt default

    config_stub.set_obj(setting, value)
    settings.init_settings()

    actual = getter(qt_settings)
    assert actual == expected


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
    """With a language set, spell check should get enabled."""
    monkeypatch.setattr(webenginesettings.spell, 'local_filename',
                        lambda _code: 'en-US-8-0')
    config_stub.val.spellcheck.languages = ['en-US']
    webenginesettings._update_settings('spellcheck.languages')
    for profile in [default_profile, private_profile]:
        assert profile.isSpellCheckEnabled()
        assert profile.spellCheckLanguages() == ['en-US-8-0']


def test_spell_check_disabled(config_stub, monkeypatch, global_settings,
                              default_profile, private_profile):
    """With no language set, spell check should get disabled."""
    config_stub.val.spellcheck.languages = []
    webenginesettings._update_settings('spellcheck.languages')
    for profile in [default_profile, private_profile]:
        assert not profile.isSpellCheckEnabled()


def test_parsed_user_agent(qapp):
    webenginesettings.init_user_agent()
    parsed = webenginesettings.parsed_user_agent
    assert parsed is not None
    assert parsed.upstream_browser_key == 'Chrome'
    assert parsed.qt_key == 'QtWebEngine'
    assert not parsed.upstream_browser_version.endswith(".0.0.0")
    assert parsed.upstream_browser_version_short.endswith(".0.0.0")


def test_profile_setter_settings(private_profile, configdata_init):
    for setting in private_profile.setter._name_to_method:
        assert setting in set(configdata.DATA)
