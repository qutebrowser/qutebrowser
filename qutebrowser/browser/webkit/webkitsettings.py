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

"""Bridge from QWebSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebSetting enum
                constants.
"""

import os.path

from PyQt5.QtGui import QFont
from PyQt5.QtWebKit import QWebSettings

from qutebrowser.config import config, websettings
from qutebrowser.utils import standarddir, objreg, urlutils, qtutils
from qutebrowser.browser import shared


class Base(websettings.Base):

    """Base settings class with appropriate _get_global_settings."""

    def _get_global_settings(self):
        return [QWebSettings.globalSettings()]


class Attribute(Base, websettings.Attribute):

    """A setting set via QWebSettings::setAttribute."""

    ENUM_BASE = QWebSettings


class Setter(Base, websettings.Setter):

    """A setting set via a QWebSettings setter method."""

    pass


class StaticSetter(Base, websettings.StaticSetter):

    """A setting set via a static QWebSettings setter method."""

    pass


class FontFamilySetter(Base, websettings.FontFamilySetter):

    """A setter for a font family.

    Gets the default value from QFont.
    """

    def __init__(self, font):
        # Mapping from QWebSettings::QWebSettings() in
        # qtwebkit/Source/WebKit/qt/Api/qwebsettings.cpp
        font_to_qfont = {
            QWebSettings.StandardFont: QFont.Serif,
            QWebSettings.FixedFont: QFont.Monospace,
            QWebSettings.SerifFont: QFont.Serif,
            QWebSettings.SansSerifFont: QFont.SansSerif,
            QWebSettings.CursiveFont: QFont.Cursive,
            QWebSettings.FantasyFont: QFont.Fantasy,
        }
        super().__init__(setter=QWebSettings.setFontFamily, font=font,
                         qfont=font_to_qfont[font])


class CookiePolicy(Base):

    """The ThirdPartyCookiePolicy setting is different from other settings."""

    MAPPING = {
        'all': QWebSettings.AlwaysAllowThirdPartyCookies,
        'no-3rdparty': QWebSettings.AlwaysBlockThirdPartyCookies,
        'never': QWebSettings.AlwaysBlockThirdPartyCookies,
        'no-unknown-3rdparty': QWebSettings.AllowThirdPartyWithExistingCookies,
    }

    def _set(self, value, settings=None):
        for obj in self._get_settings(settings):
            obj.setThirdPartyCookiePolicy(self.MAPPING[value])


def _set_user_stylesheet():
    """Set the generated user-stylesheet."""
    stylesheet = shared.get_user_stylesheet().encode('utf-8')
    url = urlutils.data_url('text/css;charset=utf-8', stylesheet)
    QWebSettings.globalSettings().setUserStyleSheetUrl(url)


def update_settings(section, option):
    """Update global settings when qwebsettings changed."""
    if section == 'ui' and option in ['hide-scrollbar', 'user-stylesheet']:
        _set_user_stylesheet()

    websettings.update_mappings(MAPPINGS, section, option)


def init(_args):
    """Initialize the global QWebSettings."""
    cache_path = standarddir.cache()
    data_path = standarddir.data()

    QWebSettings.setIconDatabasePath(standarddir.cache())
    QWebSettings.setOfflineWebApplicationCachePath(
        os.path.join(cache_path, 'application-cache'))
    QWebSettings.globalSettings().setLocalStoragePath(
        os.path.join(data_path, 'local-storage'))
    QWebSettings.setOfflineStoragePath(
        os.path.join(data_path, 'offline-storage'))

    if (config.val.private_browsing and
            not qtutils.version_check('5.4.2')):
        # WORKAROUND for https://codereview.qt-project.org/#/c/108936/
        # Won't work when private browsing is not enabled globally, but that's
        # the best we can do...
        QWebSettings.setIconDatabasePath('')

    websettings.init_mappings(MAPPINGS)
    _set_user_stylesheet()
    objreg.get('config').changed.connect(update_settings)


def shutdown():
    """Disable storage so removing tmpdir will work."""
    QWebSettings.setIconDatabasePath('')
    QWebSettings.setOfflineWebApplicationCachePath('')
    QWebSettings.globalSettings().setLocalStoragePath('')


MAPPINGS = {
    'content': {
        'allow-images':
            Attribute(QWebSettings.AutoLoadImages),
        'allow-javascript':
            Attribute(QWebSettings.JavascriptEnabled),
        'javascript-can-open-windows-automatically':
            Attribute(QWebSettings.JavascriptCanOpenWindows),
        'javascript-can-close-windows':
            Attribute(QWebSettings.JavascriptCanCloseWindows),
        'javascript-can-access-clipboard':
            Attribute(QWebSettings.JavascriptCanAccessClipboard),
        'allow-plugins':
            Attribute(QWebSettings.PluginsEnabled),
        'webgl':
            Attribute(QWebSettings.WebGLEnabled),
        'hyperlink-auditing':
            Attribute(QWebSettings.HyperlinkAuditingEnabled),
        'local-content-can-access-remote-urls':
            Attribute(QWebSettings.LocalContentCanAccessRemoteUrls),
        'local-content-can-access-file-urls':
            Attribute(QWebSettings.LocalContentCanAccessFileUrls),
        'cookies-accept':
            CookiePolicy(),
    },
    'network': {
        'dns-prefetch':
            Attribute(QWebSettings.DnsPrefetchEnabled),
    },
    'input': {
        'spatial-navigation':
            Attribute(QWebSettings.SpatialNavigationEnabled),
        'links-included-in-focus-chain':
            Attribute(QWebSettings.LinksIncludedInFocusChain),
    },
    'fonts': {
        'web-family-standard':
            FontFamilySetter(QWebSettings.StandardFont),
        'web-family-fixed':
            FontFamilySetter(QWebSettings.FixedFont),
        'web-family-serif':
            FontFamilySetter(QWebSettings.SerifFont),
        'web-family-sans-serif':
            FontFamilySetter(QWebSettings.SansSerifFont),
        'web-family-cursive':
            FontFamilySetter(QWebSettings.CursiveFont),
        'web-family-fantasy':
            FontFamilySetter(QWebSettings.FantasyFont),
        'web-size-minimum':
            Setter(QWebSettings.setFontSize,
                   args=[QWebSettings.MinimumFontSize]),
        'web-size-minimum-logical':
            Setter(QWebSettings.setFontSize,
                   args=[QWebSettings.MinimumLogicalFontSize]),
        'web-size-default':
            Setter(QWebSettings.setFontSize,
                   args=[QWebSettings.DefaultFontSize]),
        'web-size-default-fixed':
            Setter(QWebSettings.setFontSize,
                   args=[QWebSettings.DefaultFixedFontSize]),
    },
    'ui': {
        'zoom-text-only':
            Attribute(QWebSettings.ZoomTextOnly),
        'frame-flattening':
            Attribute(QWebSettings.FrameFlatteningEnabled),
        # user-stylesheet is handled separately
        'smooth-scrolling':
            Attribute(QWebSettings.ScrollAnimatorEnabled),
        #'accelerated-compositing':
        #   Attribute(QWebSettings.AcceleratedCompositingEnabled),
        #'tiled-backing-store':
        #   Attribute(QWebSettings.TiledBackingStoreEnabled),
    },
    'storage': {
        'offline-web-application-cache':
            Attribute(QWebSettings.OfflineWebApplicationCacheEnabled),
        'local-storage':
            Attribute(QWebSettings.LocalStorageEnabled,
                      QWebSettings.OfflineStorageDatabaseEnabled),
        'maximum-pages-in-cache':
            StaticSetter(QWebSettings.setMaximumPagesInCache),
    },
    'general': {
        'developer-extras':
            Attribute(QWebSettings.DeveloperExtrasEnabled),
        'print-element-backgrounds':
            Attribute(QWebSettings.PrintElementBackgrounds),
        'xss-auditing':
            Attribute(QWebSettings.XSSAuditingEnabled),
        'default-encoding':
            Setter(QWebSettings.setDefaultTextEncoding),
    }
}
