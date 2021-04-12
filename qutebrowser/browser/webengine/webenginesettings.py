# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Bridge from QWebEngineSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebEngineSetting enum
                constants.
"""

import os
import operator
from typing import cast, Any, List, Optional, Tuple, Union, TYPE_CHECKING

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineProfile

from qutebrowser.browser import history
from qutebrowser.browser.webengine import (spell, webenginequtescheme, cookies,
                                           webenginedownloads, notification)
from qutebrowser.config import config, websettings
from qutebrowser.config.websettings import AttributeInfo as Attr
from qutebrowser.utils import (standarddir, qtutils, message, log,
                               urlmatch, usertypes, objreg, version)
if TYPE_CHECKING:
    from qutebrowser.browser.webengine import interceptor

# The default QWebEngineProfile
default_profile = cast(QWebEngineProfile, None)
# The QWebEngineProfile used for private (off-the-record) windows
private_profile: Optional[QWebEngineProfile] = None
# The global WebEngineSettings object
_global_settings = cast('WebEngineSettings', None)

parsed_user_agent = None

_qute_scheme_handler = cast(webenginequtescheme.QuteSchemeHandler, None)
_req_interceptor = cast('interceptor.RequestInterceptor', None)
_download_manager = cast(webenginedownloads.DownloadManager, None)


class _SettingsWrapper:

    """Expose a QWebEngineSettings interface which acts on all profiles.

    For read operations, the default profile value is always used.
    """

    def _settings(self):
        yield default_profile.settings()
        if private_profile:
            yield private_profile.settings()

    def setAttribute(self, attribute, on):
        for settings in self._settings():
            settings.setAttribute(attribute, on)

    def setFontFamily(self, which, family):
        for settings in self._settings():
            settings.setFontFamily(which, family)

    def setFontSize(self, fonttype, size):
        for settings in self._settings():
            settings.setFontSize(fonttype, size)

    def setDefaultTextEncoding(self, encoding):
        for settings in self._settings():
            settings.setDefaultTextEncoding(encoding)

    def setUnknownUrlSchemePolicy(self, policy):
        for settings in self._settings():
            settings.setUnknownUrlSchemePolicy(policy)

    def testAttribute(self, attribute):
        return default_profile.settings().testAttribute(attribute)

    def fontSize(self, fonttype):
        return default_profile.settings().fontSize(fonttype)

    def fontFamily(self, which):
        return default_profile.settings().fontFamily(which)

    def defaultTextEncoding(self):
        return default_profile.settings().defaultTextEncoding()

    def unknownUrlSchemePolicy(self):
        return default_profile.settings().unknownUrlSchemePolicy()


class WebEngineSettings(websettings.AbstractSettings):

    """A wrapper for the config for QWebEngineSettings."""

    _ATTRIBUTES = {
        'content.xss_auditing':
            Attr(QWebEngineSettings.XSSAuditingEnabled),
        'content.images':
            Attr(QWebEngineSettings.AutoLoadImages),
        'content.javascript.enabled':
            Attr(QWebEngineSettings.JavascriptEnabled),
        'content.javascript.can_open_tabs_automatically':
            Attr(QWebEngineSettings.JavascriptCanOpenWindows),
        'content.javascript.can_access_clipboard':
            Attr(QWebEngineSettings.JavascriptCanAccessClipboard),
        'content.plugins':
            Attr(QWebEngineSettings.PluginsEnabled),
        'content.hyperlink_auditing':
            Attr(QWebEngineSettings.HyperlinkAuditingEnabled),
        'content.local_content_can_access_remote_urls':
            Attr(QWebEngineSettings.LocalContentCanAccessRemoteUrls),
        'content.local_content_can_access_file_urls':
            Attr(QWebEngineSettings.LocalContentCanAccessFileUrls),
        'content.webgl':
            Attr(QWebEngineSettings.WebGLEnabled),
        'content.local_storage':
            Attr(QWebEngineSettings.LocalStorageEnabled),
        'content.desktop_capture':
            Attr(QWebEngineSettings.ScreenCaptureEnabled,
                 converter=lambda val: True if val == 'ask' else val),
        # 'ask' is handled via the permission system

        'input.spatial_navigation':
            Attr(QWebEngineSettings.SpatialNavigationEnabled),
        'input.links_included_in_focus_chain':
            Attr(QWebEngineSettings.LinksIncludedInFocusChain),

        'scrolling.smooth':
            Attr(QWebEngineSettings.ScrollAnimatorEnabled),

        'content.print_element_backgrounds':
            Attr(QWebEngineSettings.PrintElementBackgrounds),

        'content.autoplay':
            Attr(QWebEngineSettings.PlaybackRequiresUserGesture,
                 converter=operator.not_),

        'content.dns_prefetch':
            Attr(QWebEngineSettings.DnsPrefetchEnabled),

        'tabs.favicons.show':
            Attr(QWebEngineSettings.AutoLoadIconsForPage,
                 converter=lambda val: val != 'never'),
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

    _UNKNOWN_URL_SCHEME_POLICY = {
        'disallow':
            QWebEngineSettings.DisallowUnknownUrlSchemes,
        'allow-from-user-interaction':
            QWebEngineSettings.AllowUnknownUrlSchemesFromUserInteraction,
        'allow-all':
            QWebEngineSettings.AllowAllUnknownUrlSchemes,
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

    def set_unknown_url_scheme_policy(
            self, policy: Union[str, usertypes.Unset]) -> bool:
        """Set the UnknownUrlSchemePolicy to use.

        Return:
            True if there was a change, False otherwise.
        """
        old_value = self._settings.unknownUrlSchemePolicy()
        if isinstance(policy, usertypes.Unset):
            self._settings.resetUnknownUrlSchemePolicy()
            new_value = self._settings.unknownUrlSchemePolicy()
        else:
            new_value = self._UNKNOWN_URL_SCHEME_POLICY[policy]
            self._settings.setUnknownUrlSchemePolicy(new_value)
        return old_value != new_value

    def _update_setting(self, setting, value):
        if setting == 'content.unknown_url_scheme_policy':
            return self.set_unknown_url_scheme_policy(value)
        return super()._update_setting(setting, value)

    def init_settings(self):
        super().init_settings()
        self.update_setting('content.unknown_url_scheme_policy')


class ProfileSetter:

    """Helper to set various settings on a profile."""

    def __init__(self, profile):
        self._profile = profile
        self._name_to_method = {
            'content.cache.size': self.set_http_cache_size,
            'content.cookies.store': self.set_persistent_cookie_policy,
            'spellcheck.languages': self.set_dictionary_language,
        }

        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-75884
        # (note this isn't actually fixed properly before Qt 5.15)
        header_bug_fixed = qtutils.version_check('5.15', compiled=False)
        if header_bug_fixed:
            for name in ['user_agent', 'accept_language']:
                self._name_to_method[f'content.headers.{name}'] = self.set_http_headers

    def update_setting(self, name):
        """Update a setting based on its name."""
        try:
            meth = self._name_to_method[name]
        except KeyError:
            return
        meth()

    def init_profile(self):
        """Initialize settings on the given profile."""
        self.set_http_headers()
        self.set_http_cache_size()
        self._set_hardcoded_settings()
        self.set_persistent_cookie_policy()
        self.set_dictionary_language()

    def _set_hardcoded_settings(self):
        """Set up settings with a fixed value."""
        settings = self._profile.settings()

        settings.setAttribute(
            QWebEngineSettings.FullScreenSupportEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.FocusOnNavigationEnabled, False)

        try:
            settings.setAttribute(QWebEngineSettings.PdfViewerEnabled, False)
        except AttributeError:
            # Added in Qt 5.13
            pass

    def set_http_headers(self):
        """Set the user agent and accept-language for the given profile.

        We override those per request in the URL interceptor (to allow for
        per-domain values), but this one still gets used for things like
        window.navigator.userAgent/.languages in JS.
        """
        user_agent = websettings.user_agent()
        self._profile.setHttpUserAgent(user_agent)

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
        if self._profile.isOffTheRecord():
            return
        if config.val.content.cookies.store:
            value = QWebEngineProfile.AllowPersistentCookies
        else:
            value = QWebEngineProfile.NoPersistentCookies
        self._profile.setPersistentCookiesPolicy(value)

    def set_dictionary_language(self):
        """Load the given dictionaries."""
        filenames = []
        for code in config.val.spellcheck.languages or []:
            local_filename = spell.local_filename(code)
            if not local_filename:
                if not self._profile.isOffTheRecord():
                    message.warning("Language {} is not installed - see "
                                    "scripts/dictcli.py in qutebrowser's "
                                    "sources".format(code))
                continue

            filenames.append(os.path.splitext(local_filename)[0])

        log.config.debug("Found dicts: {}".format(filenames))
        self._profile.setSpellCheckLanguages(filenames)
        self._profile.setSpellCheckEnabled(bool(filenames))


def _update_settings(option):
    """Update global settings when qwebsettings changed."""
    _global_settings.update_setting(option)
    default_profile.setter.update_setting(option)
    if private_profile:
        private_profile.setter.update_setting(option)


def _init_user_agent_str(ua):
    global parsed_user_agent
    parsed_user_agent = websettings.UserAgent.parse(ua)


def init_user_agent():
    _init_user_agent_str(QWebEngineProfile.defaultProfile().httpUserAgent())


def _init_profile(profile: QWebEngineProfile) -> None:
    """Initialize a new QWebEngineProfile.

    This currently only contains the steps which are shared between a private and a
    non-private profile (at the moment, only the default profile).
    """
    profile.setter = ProfileSetter(profile)  # type: ignore[attr-defined]
    profile.setter.init_profile()

    _qute_scheme_handler.install(profile)
    _req_interceptor.install(profile)
    _download_manager.install(profile)
    cookies.install_filter(profile)

    if notification.bridge is not None:
        notification.bridge.install(profile)

    # Clear visited links on web history clear
    history.web_history.history_cleared.connect(profile.clearAllVisitedLinks)
    history.web_history.url_cleared.connect(
        lambda url: profile.clearVisitedLinks([url]))

    _global_settings.init_settings()


def _init_default_profile():
    """Init the default QWebEngineProfile."""
    global default_profile

    default_profile = QWebEngineProfile.defaultProfile()

    assert parsed_user_agent is None  # avoid earlier profile initialization
    non_ua_version = version.qtwebengine_versions(avoid_init=True)

    init_user_agent()
    ua_version = version.qtwebengine_versions()
    if ua_version.webengine != non_ua_version.webengine:
        log.init.warning(
            "QtWebEngine version mismatch - unexpected behavior might occur, "
            "please open a bug about this.\n"
            f"  Early version: {non_ua_version}\n"
            f"  Real version:  {ua_version}")

    default_profile.setCachePath(
        os.path.join(standarddir.cache(), 'webengine'))
    default_profile.setPersistentStoragePath(
        os.path.join(standarddir.data(), 'webengine'))

    _init_profile(default_profile)


def init_private_profile():
    """Init the private QWebEngineProfile."""
    global private_profile

    if qtutils.is_single_process():
        return

    private_profile = QWebEngineProfile()
    assert private_profile.isOffTheRecord()
    _init_profile(private_profile)


def _init_site_specific_quirks():
    """Add custom user-agent settings for problematic sites.

    See https://github.com/qutebrowser/qutebrowser/issues/4810
    """
    if not config.val.content.site_specific_quirks.enabled:
        return

    # Please leave this here as a template for new UAs.
    # default_ua = ("Mozilla/5.0 ({os_info}) "
    #               "AppleWebKit/{webkit_version} (KHTML, like Gecko) "
    #               "{qt_key}/{qt_version} "
    #               "{upstream_browser_key}/{upstream_browser_version} "
    #               "Safari/{webkit_version}")
    no_qtwe_ua = ("Mozilla/5.0 ({os_info}) "
                  "AppleWebKit/{webkit_version} (KHTML, like Gecko) "
                  "{upstream_browser_key}/{upstream_browser_version} "
                  "Safari/{webkit_version}")
    new_chrome_ua = ("Mozilla/5.0 ({os_info}) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/99 "
                     "Safari/537.36")
    edge_ua = ("Mozilla/5.0 ({os_info}) "
               "AppleWebKit/{webkit_version} (KHTML, like Gecko) "
               "{upstream_browser_key}/{upstream_browser_version} "
               "Safari/{webkit_version} "
               "Edg/{upstream_browser_version}")

    user_agents = [
        # Needed to avoid a ""WhatsApp works with Google Chrome 36+" error
        # page which doesn't allow to use WhatsApp Web at all. Also see the
        # additional JS quirk: qutebrowser/javascript/quirks/whatsapp_web.user.js
        # https://github.com/qutebrowser/qutebrowser/issues/4445
        ("ua-whatsapp", 'https://web.whatsapp.com/', no_qtwe_ua),

        # Needed to avoid a "you're using a browser [...] that doesn't allow us
        # to keep your account secure" error.
        # https://github.com/qutebrowser/qutebrowser/issues/5182
        ("ua-google", 'https://accounts.google.com/*', edge_ua),

        # Needed because Slack adds an error which prevents using it relatively
        # aggressively, despite things actually working fine.
        # September 2020: Qt 5.12 works, but Qt <= 5.11 shows the error.
        # https://github.com/qutebrowser/qutebrowser/issues/4669
        ("ua-slack", 'https://*.slack.com/*', new_chrome_ua),
    ]

    for name, pattern, ua in user_agents:
        if name not in config.val.content.site_specific_quirks.skip:
            config.instance.set_obj('content.headers.user_agent', ua,
                                    pattern=urlmatch.UrlPattern(pattern),
                                    hide_userconfig=True)

    if 'misc-krunker' not in config.val.content.site_specific_quirks.skip:
        config.instance.set_obj(
            'content.headers.accept_language',
            '',
            pattern=urlmatch.UrlPattern('https://matchmaker.krunker.io/*'),
            hide_userconfig=True,
        )


def _init_devtools_settings():
    """Make sure the devtools always get images/JS permissions."""
    settings: List[Tuple[str, Any]] = [
        ('content.javascript.enabled', True),
        ('content.images', True),
        ('content.cookies.accept', 'all'),
    ]

    for setting, value in settings:
        for pattern in ['chrome-devtools://*', 'devtools://*']:
            config.instance.set_obj(setting, value,
                                    pattern=urlmatch.UrlPattern(pattern),
                                    hide_userconfig=True)


def init():
    """Initialize the global QWebSettings."""
    webenginequtescheme.init()
    spell.init()

    # For some reason we need to keep a reference, otherwise the scheme handler
    # won't work...
    # https://www.riverbankcomputing.com/pipermail/pyqt/2016-September/038075.html
    global _qute_scheme_handler
    app = QApplication.instance()
    log.init.debug("Initializing qute://* handler...")
    _qute_scheme_handler = webenginequtescheme.QuteSchemeHandler(parent=app)

    global _req_interceptor
    log.init.debug("Initializing request interceptor...")
    from qutebrowser.browser.webengine import interceptor
    _req_interceptor = interceptor.RequestInterceptor(parent=app)

    global _download_manager
    log.init.debug("Initializing QtWebEngine downloads...")
    _download_manager = webenginedownloads.DownloadManager(parent=app)
    objreg.register('webengine-download-manager', _download_manager)
    from qutebrowser.misc import quitter
    quitter.instance.shutting_down.connect(_download_manager.shutdown)

    log.init.debug("Initializing notification presenter...")
    notification.init()

    log.init.debug("Initializing global settings...")
    global _global_settings
    _global_settings = WebEngineSettings(_SettingsWrapper())

    log.init.debug("Initializing profiles...")
    _init_default_profile()
    init_private_profile()
    config.instance.changed.connect(_update_settings)

    log.init.debug("Misc initialization...")
    _init_site_specific_quirks()
    _init_devtools_settings()


def shutdown():
    pass
