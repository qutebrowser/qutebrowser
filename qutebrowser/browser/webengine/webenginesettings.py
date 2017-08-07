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
import sys
import ctypes
import ctypes.util

from PyQt5.QtGui import QFont
from PyQt5.QtWebEngineWidgets import (QWebEngineSettings, QWebEngineProfile,
                                      QWebEngineScript)

from qutebrowser.browser import shared
from qutebrowser.config import config, websettings
from qutebrowser.utils import objreg, utils, standarddir, javascript, qtutils


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

    def __init__(self, setter, default=websettings.UNSET):
        super().__init__(default)
        self._setter = setter

    def __repr__(self):
        return utils.get_repr(self, setter=self._setter, constructor=True)

    def _set(self, value, settings=None):
        if settings is not None:
            raise ValueError("'settings' may not be set with "
                             "DefaultProfileSetters!")
        setter = getattr(default_profile, self._setter)
        setter(value)


class PersistentCookiePolicy(DefaultProfileSetter):

    """The cookies -> store setting is different from other settings."""

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


def _set_user_agent(profile):
    """Set the user agent for the given profile.

    We override this per request in the URL interceptor (to allow for
    per-domain user agents), but this one still gets used for things like
    window.navigator.userAgent in JS.
    """
    user_agent = config.get('network', 'user-agent')
    profile.setHttpUserAgent(user_agent)


def update_settings(section, option):
    """Update global settings when qwebsettings changed."""
    websettings.update_mappings(MAPPINGS, section, option)
    if section == 'ui' and option in ['hide-scrollbar', 'user-stylesheet']:
        _init_stylesheet(default_profile)
        _init_stylesheet(private_profile)
    elif section == 'network' and option == 'user-agent':
        _set_user_agent(default_profile)
        _set_user_agent(private_profile)


def _init_profiles():
    """Init the two used QWebEngineProfiles."""
    global default_profile, private_profile
    default_profile = QWebEngineProfile.defaultProfile()
    default_profile.setCachePath(
        os.path.join(standarddir.cache(), 'webengine'))
    default_profile.setPersistentStoragePath(
        os.path.join(standarddir.data(), 'webengine'))
    _init_stylesheet(default_profile)
    _set_user_agent(default_profile)

    private_profile = QWebEngineProfile()
    assert private_profile.isOffTheRecord()
    _init_stylesheet(private_profile)
    _set_user_agent(private_profile)


def init(args):
    """Initialize the global QWebSettings."""
    if args.enable_webengine_inspector:
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = str(utils.random_port())

    # WORKAROUND for
    # https://bugs.launchpad.net/ubuntu/+source/python-qt4/+bug/941826
    if sys.platform == 'linux':
        ctypes.CDLL(ctypes.util.find_library("GL"), mode=ctypes.RTLD_GLOBAL)

    _init_profiles()

    # We need to do this here as a WORKAROUND for
    # https://bugreports.qt.io/browse/QTBUG-58650
    if not qtutils.version_check('5.9'):
        PersistentCookiePolicy().set(config.get('content', 'cookies-store'))
    Attribute(QWebEngineSettings.FullScreenSupportEnabled).set(True)

    websettings.init_mappings(MAPPINGS)
    objreg.get('config').changed.connect(update_settings)


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
    'content': {
        'allow-images':
            Attribute(QWebEngineSettings.AutoLoadImages),
        'allow-javascript':
            Attribute(QWebEngineSettings.JavascriptEnabled),
        'javascript-can-open-windows-automatically':
            Attribute(QWebEngineSettings.JavascriptCanOpenWindows),
        'javascript-can-access-clipboard':
            Attribute(QWebEngineSettings.JavascriptCanAccessClipboard),
        'allow-plugins':
            Attribute(QWebEngineSettings.PluginsEnabled),
        'hyperlink-auditing':
            Attribute(QWebEngineSettings.HyperlinkAuditingEnabled),
        'local-content-can-access-remote-urls':
            Attribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls),
        'local-content-can-access-file-urls':
            Attribute(QWebEngineSettings.LocalContentCanAccessFileUrls),
        'webgl':
            Attribute(QWebEngineSettings.WebGLEnabled),
    },
    'input': {
        'spatial-navigation':
            Attribute(QWebEngineSettings.SpatialNavigationEnabled),
        'links-included-in-focus-chain':
            Attribute(QWebEngineSettings.LinksIncludedInFocusChain),
    },
    'fonts': {
        'web-family-standard':
            FontFamilySetter(QWebEngineSettings.StandardFont),
        'web-family-fixed':
            FontFamilySetter(QWebEngineSettings.FixedFont),
        'web-family-serif':
            FontFamilySetter(QWebEngineSettings.SerifFont),
        'web-family-sans-serif':
            FontFamilySetter(QWebEngineSettings.SansSerifFont),
        'web-family-cursive':
            FontFamilySetter(QWebEngineSettings.CursiveFont),
        'web-family-fantasy':
            FontFamilySetter(QWebEngineSettings.FantasyFont),
        'web-size-minimum':
            Setter(QWebEngineSettings.setFontSize,
                   args=[QWebEngineSettings.MinimumFontSize]),
        'web-size-minimum-logical':
            Setter(QWebEngineSettings.setFontSize,
                   args=[QWebEngineSettings.MinimumLogicalFontSize]),
        'web-size-default':
            Setter(QWebEngineSettings.setFontSize,
                   args=[QWebEngineSettings.DefaultFontSize]),
        'web-size-default-fixed':
            Setter(QWebEngineSettings.setFontSize,
                   args=[QWebEngineSettings.DefaultFixedFontSize]),
    },
    'ui': {
        'smooth-scrolling':
            Attribute(QWebEngineSettings.ScrollAnimatorEnabled),
    },
    'storage': {
        'local-storage':
            Attribute(QWebEngineSettings.LocalStorageEnabled),
        'cache-size':
            # 0: automatically managed by QtWebEngine
            DefaultProfileSetter('setHttpCacheMaximumSize', default=0),
    },
    'general': {
        'xss-auditing':
            Attribute(QWebEngineSettings.XSSAuditingEnabled),
        'default-encoding':
            Setter(QWebEngineSettings.setDefaultTextEncoding),
    }
}

try:
    MAPPINGS['general']['print-element-backgrounds'] = Attribute(
        QWebEngineSettings.PrintElementBackgrounds)
except AttributeError:
    # Added in Qt 5.8
    pass


if qtutils.version_check('5.9'):
    # https://bugreports.qt.io/browse/QTBUG-58650
    MAPPINGS['content']['cookies-store'] = PersistentCookiePolicy()
