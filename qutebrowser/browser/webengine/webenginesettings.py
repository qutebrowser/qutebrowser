# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# We get various "abstract but not overridden" warnings
# pylint: disable=abstract-method

"""Bridge from QWebEngineSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebEngineSetting enum
                constants.
"""

import os

from PyQt5.QtGui import QFont
from PyQt5.QtWebEngineWidgets import (QWebEngineSettings, QWebEngineProfile,
                                      QWebEngineScript)

from qutebrowser.browser import shared
from qutebrowser.browser.webengine import spell
from qutebrowser.config import config, websettings
from qutebrowser.utils import utils, standarddir, javascript, qtutils, message

# The default QWebEngineProfile
default_profile = None
# The QWebEngineProfile used for private (off-the-record) windows
private_profile = None


class Base(websettings.Base):

    """Base settings class with appropriate _get_global_settings."""

    def _get_global_settings(self):
        return [default_profile.settings(), private_profile.settings()]


class Attribute(Base, websettings.Attribute):

    """A setting set via QWebEngineSettings::setAttribute."""

    ENUM_BASE = QWebEngineSettings


class Setter(Base, websettings.Setter):

    """A setting set via a QWebEngineSettings setter method."""

    pass


class FontFamilySetter(Base, websettings.FontFamilySetter):

    """A setter for a font family.

    Gets the default value from QFont.
    """

    def __init__(self, font):
        # Mapping from WebEngineSettings::initDefaults in
        # qtwebengine/src/core/web_engine_settings.cpp
        font_to_qfont = {
            QWebEngineSettings.StandardFont: QFont.Serif,
            QWebEngineSettings.FixedFont: QFont.Monospace,
            QWebEngineSettings.SerifFont: QFont.Serif,
            QWebEngineSettings.SansSerifFont: QFont.SansSerif,
            QWebEngineSettings.CursiveFont: QFont.Cursive,
            QWebEngineSettings.FantasyFont: QFont.Fantasy,
        }
        super().__init__(setter=QWebEngineSettings.setFontFamily, font=font,
                         qfont=font_to_qfont[font])


class DefaultProfileSetter(websettings.Base):

    """A setting set on the QWebEngineProfile."""

    def __init__(self, setter, converter=None, default=websettings.UNSET):
        super().__init__(default)
        self._setter = setter
        self._converter = converter

    def __repr__(self):
        return utils.get_repr(self, setter=self._setter, constructor=True)

    def _set(self, value, settings=None):
        if settings is not None:
            raise ValueError("'settings' may not be set with "
                             "DefaultProfileSetters!")

        setter = getattr(default_profile, self._setter)
        if self._converter is not None:
            value = self._converter(value)

        setter(value)


class PersistentCookiePolicy(DefaultProfileSetter):

    """The content.cookies.store setting is different from other settings."""

    def __init__(self):
        super().__init__('setPersistentCookiesPolicy')

    def _set(self, value, settings=None):
        if settings is not None:
            raise ValueError("'settings' may not be set with "
                             "PersistentCookiePolicy!")
        setter = getattr(QWebEngineProfile.defaultProfile(), self._setter)
        setter(
            QWebEngineProfile.AllowPersistentCookies if value else
            QWebEngineProfile.NoPersistentCookies
        )


class DictionaryLanguageSetter(DefaultProfileSetter):

    """Sets paths to dictionary files based on language codes."""

    def __init__(self):
        super().__init__('setSpellCheckLanguages', default=[])

    def _find_installed(self, code):
        installed_file = spell.installed_file(code)
        if not installed_file:
            message.warning(
                "Language {} is not installed - see scripts/install_dict.py "
                "in qutebrowser's sources".format(code))
        return installed_file

    def _set(self, value, settings=None):
        if settings is not None:
            raise ValueError("'settings' may not be set with "
                             "DictionaryLanguageSetter!")
        filenames = [self._find_installed(code) for code in value]
        super()._set([f for f in filenames if f], settings)


def _init_stylesheet(profile):
    """Initialize custom stylesheets.

    Mostly inspired by QupZilla:
    https://github.com/QupZilla/qupzilla/blob/v2.0/src/lib/app/mainapplication.cpp#L1063-L1101
    https://github.com/QupZilla/qupzilla/blob/v2.0/src/lib/tools/scripts.cpp#L119-L132
    """
    old_script = profile.scripts().findScript('_qute_stylesheet')
    if not old_script.isNull():
        profile.scripts().remove(old_script)

    css = shared.get_user_stylesheet()
    source = """
        (function() {{
            var css = document.createElement('style');
            css.setAttribute('type', 'text/css');
            css.appendChild(document.createTextNode('{}'));
            document.getElementsByTagName('head')[0].appendChild(css);
        }})()
    """.format(javascript.string_escape(css))

    script = QWebEngineScript()
    script.setName('_qute_stylesheet')
    script.setInjectionPoint(QWebEngineScript.DocumentReady)
    script.setWorldId(QWebEngineScript.ApplicationWorld)
    script.setRunsOnSubFrames(True)
    script.setSourceCode(source)
    profile.scripts().insert(script)


def _set_http_headers(profile):
    """Set the user agent and accept-language for the given profile.

    We override those per request in the URL interceptor (to allow for
    per-domain values), but this one still gets used for things like
    window.navigator.userAgent/.languages in JS.
    """
    profile.setHttpUserAgent(config.val.content.headers.user_agent)
    accept_language = config.val.content.headers.accept_language
    if accept_language is not None:
        profile.setHttpAcceptLanguage(accept_language)


def _update_settings(option):
    """Update global settings when qwebsettings changed."""
    websettings.update_mappings(MAPPINGS, option)
    if option in ['scrolling.bar', 'content.user_stylesheets']:
        _init_stylesheet(default_profile)
        _init_stylesheet(private_profile)
    elif option in ['content.headers.user_agent',
                    'content.headers.accept_language']:
        _set_http_headers(default_profile)
        _set_http_headers(private_profile)


def _init_profiles():
    """Init the two used QWebEngineProfiles."""
    global default_profile, private_profile
    default_profile = QWebEngineProfile.defaultProfile()
    default_profile.setCachePath(
        os.path.join(standarddir.cache(), 'webengine'))
    default_profile.setPersistentStoragePath(
        os.path.join(standarddir.data(), 'webengine'))
    _init_stylesheet(default_profile)
    _set_http_headers(default_profile)

    private_profile = QWebEngineProfile()
    assert private_profile.isOffTheRecord()
    _init_stylesheet(private_profile)
    _set_http_headers(private_profile)

    if qtutils.version_check('5.8'):
        default_profile.setSpellCheckEnabled(True)
        private_profile.setSpellCheckEnabled(True)


def init(args):
    """Initialize the global QWebSettings."""
    if args.enable_webengine_inspector:
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = str(utils.random_port())

    _init_profiles()

    # We need to do this here as a WORKAROUND for
    # https://bugreports.qt.io/browse/QTBUG-58650
    if not qtutils.version_check('5.9', compiled=False):
        PersistentCookiePolicy().set(config.val.content.cookies.store)
    Attribute(QWebEngineSettings.FullScreenSupportEnabled).set(True)

    websettings.init_mappings(MAPPINGS)
    config.instance.changed.connect(_update_settings)


def shutdown():
    # FIXME:qtwebengine do we need to do something for a clean shutdown here?
    pass


# Missing QtWebEngine attributes:
# - ScreenCaptureEnabled
# - Accelerated2dCanvasEnabled
# - AutoLoadIconsForPage
# - TouchIconsEnabled
# - FocusOnNavigationEnabled (5.8)
# - AllowRunningInsecureContent (5.8)
#
# Missing QtWebEngine fonts:
# - PictographFont


MAPPINGS = {
    'content.images':
        Attribute(QWebEngineSettings.AutoLoadImages),
    'content.javascript.enabled':
        Attribute(QWebEngineSettings.JavascriptEnabled),
    'content.javascript.can_open_tabs_automatically':
        Attribute(QWebEngineSettings.JavascriptCanOpenWindows),
    'content.javascript.can_access_clipboard':
        Attribute(QWebEngineSettings.JavascriptCanAccessClipboard),
    'content.plugins':
        Attribute(QWebEngineSettings.PluginsEnabled),
    'content.hyperlink_auditing':
        Attribute(QWebEngineSettings.HyperlinkAuditingEnabled),
    'content.local_content_can_access_remote_urls':
        Attribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls),
    'content.local_content_can_access_file_urls':
        Attribute(QWebEngineSettings.LocalContentCanAccessFileUrls),
    'content.webgl':
        Attribute(QWebEngineSettings.WebGLEnabled),
    'content.local_storage':
        Attribute(QWebEngineSettings.LocalStorageEnabled),
    'content.cache.size':
        # 0: automatically managed by QtWebEngine
        DefaultProfileSetter('setHttpCacheMaximumSize', default=0,
                             converter=lambda val:
                             qtutils.check_overflow(val, 'int', fatal=False)),
    'content.xss_auditing':
        Attribute(QWebEngineSettings.XSSAuditingEnabled),
    'content.default_encoding':
        Setter(QWebEngineSettings.setDefaultTextEncoding),

    'input.spatial_navigation':
        Attribute(QWebEngineSettings.SpatialNavigationEnabled),
    'input.links_included_in_focus_chain':
        Attribute(QWebEngineSettings.LinksIncludedInFocusChain),

    'fonts.web.family.standard':
        FontFamilySetter(QWebEngineSettings.StandardFont),
    'fonts.web.family.fixed':
        FontFamilySetter(QWebEngineSettings.FixedFont),
    'fonts.web.family.serif':
        FontFamilySetter(QWebEngineSettings.SerifFont),
    'fonts.web.family.sans_serif':
        FontFamilySetter(QWebEngineSettings.SansSerifFont),
    'fonts.web.family.cursive':
        FontFamilySetter(QWebEngineSettings.CursiveFont),
    'fonts.web.family.fantasy':
        FontFamilySetter(QWebEngineSettings.FantasyFont),
    'fonts.web.size.minimum':
        Setter(QWebEngineSettings.setFontSize,
               args=[QWebEngineSettings.MinimumFontSize]),
    'fonts.web.size.minimum_logical':
        Setter(QWebEngineSettings.setFontSize,
               args=[QWebEngineSettings.MinimumLogicalFontSize]),
    'fonts.web.size.default':
        Setter(QWebEngineSettings.setFontSize,
               args=[QWebEngineSettings.DefaultFontSize]),
    'fonts.web.size.default_fixed':
        Setter(QWebEngineSettings.setFontSize,
               args=[QWebEngineSettings.DefaultFixedFontSize]),

    'scrolling.smooth':
        Attribute(QWebEngineSettings.ScrollAnimatorEnabled),
}

try:
    MAPPINGS['content.print_element_backgrounds'] = Attribute(
        QWebEngineSettings.PrintElementBackgrounds)
except AttributeError:
    # Added in Qt 5.8
    pass


if qtutils.version_check('5.8'):
    MAPPINGS['spellcheck.languages'] = DictionaryLanguageSetter()


if qtutils.version_check('5.9', compiled=False):
    # https://bugreports.qt.io/browse/QTBUG-58650
    MAPPINGS['content.cookies.store'] = PersistentCookiePolicy()
