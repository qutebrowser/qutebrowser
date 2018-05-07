# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Bridge from QWebEngineSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebEngineSetting enum
                constants.
"""

import os

from PyQt5.QtGui import QFont
from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineProfile

from qutebrowser.browser.webengine import spell
from qutebrowser.config import config, websettings
from qutebrowser.utils import utils, standarddir, qtutils, message, log

# The default QWebEngineProfile
default_profile = None
# The QWebEngineProfile used for private (off-the-record) windows
private_profile = None
# The global WebEngineSettings object
global_settings = None


class _SettingsWrapper:

    """Expose a QWebEngineSettings interface which acts on all profiles.

    For read operations, the default profile value is always used.
    """

    def __init__(self):
        self._settings = [default_profile.settings(),
                          private_profile.settings()]

    def setAttribute(self, *args, **kwargs):
        for settings in self._settings:
            settings.setAttribute(*args, **kwargs)

    def setFontFamily(self, *args, **kwargs):
        for settings in self._settings:
            settings.setFontFamily(*args, **kwargs)

    def setFontSize(self, *args, **kwargs):
        for settings in self._settings:
            settings.setFontSize(*args, **kwargs)

    def setDefaultTextEncoding(self, *args, **kwargs):
        for settings in self._settings:
            settings.setDefaultTextEncoding(*args, **kwargs)

    def testAttribute(self, *args, **kwargs):
        return self._settings[0].testAttribute(*args, **kwargs)

    def fontSize(self, *args, **kwargs):
        return self._settings[0].fontSize(*args, **kwargs)

    def fontFamily(self, *args, **kwargs):
        return self._settings[0].fontFamily(*args, **kwargs)

    def defaultTextEncoding(self, *args, **kwargs):
        return self._settings[0].defaultTextEncoding(*args, **kwargs)


class WebEngineSettings(websettings.AbstractSettings):

    """A wrapper for the config for QWebEngineSettings."""

    _ATTRIBUTES = {
        'content.xss_auditing':
            [QWebEngineSettings.XSSAuditingEnabled],
        'content.images':
            [QWebEngineSettings.AutoLoadImages],
        'content.javascript.enabled':
            [QWebEngineSettings.JavascriptEnabled],
        'content.javascript.can_open_tabs_automatically':
            [QWebEngineSettings.JavascriptCanOpenWindows],
        'content.javascript.can_access_clipboard':
            [QWebEngineSettings.JavascriptCanAccessClipboard],
        'content.plugins':
            [QWebEngineSettings.PluginsEnabled],
        'content.hyperlink_auditing':
            [QWebEngineSettings.HyperlinkAuditingEnabled],
        'content.local_content_can_access_remote_urls':
            [QWebEngineSettings.LocalContentCanAccessRemoteUrls],
        'content.local_content_can_access_file_urls':
            [QWebEngineSettings.LocalContentCanAccessFileUrls],
        'content.webgl':
            [QWebEngineSettings.WebGLEnabled],
        'content.local_storage':
            [QWebEngineSettings.LocalStorageEnabled],

        'input.spatial_navigation':
            [QWebEngineSettings.SpatialNavigationEnabled],
        'input.links_included_in_focus_chain':
            [QWebEngineSettings.LinksIncludedInFocusChain],

        'scrolling.smooth':
            [QWebEngineSettings.ScrollAnimatorEnabled],
    }

    _FONT_SIZES = {
        'fonts.web.size.minimum':
            QWebEngineSettings.MinimumFontSize,
        'fonts.web.size.minimum_logical':
            QWebEngineSettings.MinimumLogicalFontSize,
        'fonts.web.size.default':
            QWebEngineSettings.DefaultFontSize,
        'fonts.web.size.default_fixed':
            QWebEngineSettings.DefaultFixedFontSize,
    }

    _FONT_FAMILIES = {
        'fonts.web.family.standard': QWebEngineSettings.StandardFont,
        'fonts.web.family.fixed': QWebEngineSettings.FixedFont,
        'fonts.web.family.serif': QWebEngineSettings.SerifFont,
        'fonts.web.family.sans_serif': QWebEngineSettings.SansSerifFont,
        'fonts.web.family.cursive': QWebEngineSettings.CursiveFont,
        'fonts.web.family.fantasy': QWebEngineSettings.FantasyFont,
    }

    # Mapping from WebEngineSettings::initDefaults in
    # qtwebengine/src/core/web_engine_settings.cpp
    _FONT_TO_QFONT = {
        QWebEngineSettings.StandardFont: QFont.Serif,
        QWebEngineSettings.FixedFont: QFont.Monospace,
        QWebEngineSettings.SerifFont: QFont.Serif,
        QWebEngineSettings.SansSerifFont: QFont.SansSerif,
        QWebEngineSettings.CursiveFont: QFont.Cursive,
        QWebEngineSettings.FantasyFont: QFont.Fantasy,
    }

    def __init__(self, settings):
        super().__init__(settings)
        # Attributes which don't exist in all Qt versions.
        new_attributes = {
            # Qt 5.8
            'content.print_element_backgrounds': 'PrintElementBackgrounds',
        }
        for name, attribute in new_attributes.items():
            try:
                value = getattr(QWebEngineSettings, attribute)
            except AttributeError:
                continue

            self._ATTRIBUTES[name] = [value]


class ProfileSetter:

    """Helper to set various settings on a profile."""

    def __init__(self, profile):
        self._profile = profile

    def init_profile(self):
        """Initialize settings on the given profile."""
        self.set_http_headers()
        self.set_http_cache_size()
        self._profile.settings().setAttribute(
            QWebEngineSettings.FullScreenSupportEnabled, True)
        if qtutils.version_check('5.8'):
            self.set_dictionary_language()

    def set_http_headers(self):
        """Set the user agent and accept-language for the given profile.

        We override those per request in the URL interceptor (to allow for
        per-domain values), but this one still gets used for things like
        window.navigator.userAgent/.languages in JS.
        """
        self._profile.setHttpUserAgent(config.val.content.headers.user_agent)
        accept_language = config.val.content.headers.accept_language
        if accept_language is not None:
            self._profile.setHttpAcceptLanguage(accept_language)

    def set_http_cache_size(self):
        """Initialize the HTTP cache size for the given profile."""
        size = config.val.content.cache.size
        if size is None:
            size = 0
        else:
            size = qtutils.check_overflow(size, 'int', fatal=False)

        # 0: automatically managed by QtWebEngine
        self._profile.setHttpCacheMaximumSize(size)

    def set_persistent_cookie_policy(self):
        """Set the HTTP Cookie size for the given profile."""
        assert not self._profile.isOffTheRecord()
        if config.val.content.cookies.store:
            value = QWebEngineProfile.AllowPersistentCookies
        else:
            value = QWebEngineProfile.NoPersistentCookies
        self._profile.setPersistentCookiesPolicy(value)

    def set_dictionary_language(self, warn=True):
        """Load the given dictionaries."""
        filenames = []
        for code in config.val.spellcheck.languages or []:
            local_filename = spell.local_filename(code)
            if not local_filename:
                if warn:
                    message.warning("Language {} is not installed - see "
                                    "scripts/dictcli.py in qutebrowser's "
                                    "sources".format(code))
                continue

            filenames.append(local_filename)

        log.config.debug("Found dicts: {}".format(filenames))
        self._profile.setSpellCheckLanguages(filenames)
        self._profile.setSpellCheckEnabled(bool(filenames))


def _update_settings(option):
    """Update global settings when qwebsettings changed."""
    global_settings.update_setting(option)

    if option in ['content.headers.user_agent',
                  'content.headers.accept_language']:
        default_profile.setter.set_http_headers()
        private_profile.setter.set_http_headers()
    elif option == 'content.cache.size':
        default_profile.setter.set_http_cache_size()
        private_profile.setter.set_http_cache_size()
    elif (option == 'content.cookies.store' and
          # https://bugreports.qt.io/browse/QTBUG-58650
          qtutils.version_check('5.9', compiled=False)):
        default_profile.setter.set_persistent_cookie_policy()
        # We're not touching the private profile's cookie policy.
    elif option == 'spellcheck.languages':
        default_profile.setter.set_dictionary_language()
        private_profile.setter.set_dictionary_language(warn=False)


def _init_profiles():
    """Init the two used QWebEngineProfiles."""
    global default_profile, private_profile

    default_profile = QWebEngineProfile.defaultProfile()
    default_profile.setter = ProfileSetter(default_profile)
    default_profile.setCachePath(
        os.path.join(standarddir.cache(), 'webengine'))
    default_profile.setPersistentStoragePath(
        os.path.join(standarddir.data(), 'webengine'))
    default_profile.setter.init_profile()
    default_profile.setter.set_persistent_cookie_policy()

    private_profile = QWebEngineProfile()
    private_profile.setter = ProfileSetter(private_profile)
    assert private_profile.isOffTheRecord()
    private_profile.setter.init_profile()


def init(args):
    """Initialize the global QWebSettings."""
    if args.enable_webengine_inspector:
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = str(utils.random_port())

    _init_profiles()
    config.instance.changed.connect(_update_settings)

    global global_settings
    global_settings = WebEngineSettings(_SettingsWrapper())
    global_settings.init_settings()


def shutdown():
    pass
