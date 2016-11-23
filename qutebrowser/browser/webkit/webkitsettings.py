# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Bridge from QWebSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebSetting enum
                constants.
"""

import os.path

from PyQt5.QtWebKit import QWebSettings

from qutebrowser.config import config, websettings
from qutebrowser.utils import standarddir, objreg, urlutils
from qutebrowser.browser import shared


class Attribute(websettings.Attribute):

    """A setting set via QWebSettings::setAttribute."""

    GLOBAL_SETTINGS = QWebSettings.globalSettings
    ENUM_BASE = QWebSettings


class Setter(websettings.Setter):

    """A setting set via QWebSettings getter/setter methods."""

    GLOBAL_SETTINGS = QWebSettings.globalSettings


class NullStringSetter(websettings.NullStringSetter):

    """A setter for settings requiring a null QString as default."""

    GLOBAL_SETTINGS = QWebSettings.globalSettings


class StaticSetter(websettings.StaticSetter):

    """A setting set via static QWebSettings getter/setter methods."""

    GLOBAL_SETTINGS = QWebSettings.globalSettings


class CookiePolicy(websettings.Base):

    """The ThirdPartyCookiePolicy setting is different from other settings."""

    MAPPING = {
        'all': QWebSettings.AlwaysAllowThirdPartyCookies,
        'no-3rdparty': QWebSettings.AlwaysBlockThirdPartyCookies,
        'never': QWebSettings.AlwaysBlockThirdPartyCookies,
        'no-unknown-3rdparty': QWebSettings.AllowThirdPartyWithExistingCookies,
    }

    def get(self, settings=None):
        return config.get('content', 'cookies-accept')

    def _set(self, value, settings=None):
        QWebSettings.globalSettings().setThirdPartyCookiePolicy(
            self.MAPPING[value])


def _set_user_stylesheet():
    """Set the generated user-stylesheet."""
    stylesheet = shared.get_user_stylesheet().encode('utf-8')
    url = urlutils.data_url('text/css;charset=utf-8', stylesheet)
    QWebSettings.globalSettings().setUserStyleSheetUrl(url)


def update_settings(section, option):
    """Update global settings when qwebsettings changed."""
    if (section, option) == ('general', 'private-browsing'):
        cache_path = standarddir.cache()
        if config.get('general', 'private-browsing') or cache_path is None:
            QWebSettings.setIconDatabasePath('')
        else:
            QWebSettings.setIconDatabasePath(cache_path)
    elif section == 'ui' and option in ['hide-scrollbar', 'user-stylesheet']:
        _set_user_stylesheet()

    websettings.update_mappings(MAPPINGS, section, option)


def init(_args):
    """Initialize the global QWebSettings."""
    cache_path = standarddir.cache()
    data_path = standarddir.data()
    if config.get('general', 'private-browsing'):
        QWebSettings.setIconDatabasePath('')
    else:
        QWebSettings.setIconDatabasePath(cache_path)

    QWebSettings.setOfflineWebApplicationCachePath(
        os.path.join(cache_path, 'application-cache'))
    QWebSettings.globalSettings().setLocalStoragePath(
        os.path.join(data_path, 'local-storage'))
    QWebSettings.setOfflineStoragePath(
        os.path.join(data_path, 'offline-storage'))

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
        #'allow-java':
        #   Attribute(QWebSettings.JavaEnabled),
        'allow-plugins':
            Attribute(QWebSettings.PluginsEnabled),
        'webgl':
            Attribute(QWebSettings.WebGLEnabled),
        'css-regions':
            Attribute(QWebSettings.CSSRegionsEnabled),
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
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.StandardFont]),
        'web-family-fixed':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.FixedFont]),
        'web-family-serif':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.SerifFont]),
        'web-family-sans-serif':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.SansSerifFont]),
        'web-family-cursive':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.CursiveFont]),
        'web-family-fantasy':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.FantasyFont]),
        'web-size-minimum':
            Setter(getter=QWebSettings.fontSize,
                   setter=QWebSettings.setFontSize,
                   args=[QWebSettings.MinimumFontSize]),
        'web-size-minimum-logical':
            Setter(getter=QWebSettings.fontSize,
                   setter=QWebSettings.setFontSize,
                   args=[QWebSettings.MinimumLogicalFontSize]),
        'web-size-default':
            Setter(getter=QWebSettings.fontSize,
                   setter=QWebSettings.setFontSize,
                   args=[QWebSettings.DefaultFontSize]),
        'web-size-default-fixed':
            Setter(getter=QWebSettings.fontSize,
                   setter=QWebSettings.setFontSize,
                   args=[QWebSettings.DefaultFixedFontSize]),
    },
    'ui': {
        'zoom-text-only':
            Attribute(QWebSettings.ZoomTextOnly),
        'frame-flattening':
            Attribute(QWebSettings.FrameFlatteningEnabled),
        # user-stylesheet is handled separately
        'css-media-type':
            NullStringSetter(getter=QWebSettings.cssMediaType,
                             setter=QWebSettings.setCSSMediaType),
        'smooth-scrolling':
            Attribute(QWebSettings.ScrollAnimatorEnabled),
        #'accelerated-compositing':
        #   Attribute(QWebSettings.AcceleratedCompositingEnabled),
        #'tiled-backing-store':
        #   Attribute(QWebSettings.TiledBackingStoreEnabled),
    },
    'storage': {
        'offline-storage-database':
            Attribute(QWebSettings.OfflineStorageDatabaseEnabled),
        'offline-web-application-storage':
            Attribute(QWebSettings.OfflineWebApplicationCacheEnabled),
        'local-storage':
            Attribute(QWebSettings.LocalStorageEnabled),
        'maximum-pages-in-cache':
            StaticSetter(getter=QWebSettings.maximumPagesInCache,
                         setter=QWebSettings.setMaximumPagesInCache),
        'object-cache-capacities':
            StaticSetter(getter=None,
                         setter=QWebSettings.setObjectCacheCapacities,
                         unpack=True),
        'offline-storage-default-quota':
            StaticSetter(getter=QWebSettings.offlineStorageDefaultQuota,
                         setter=QWebSettings.setOfflineStorageDefaultQuota),
        'offline-web-application-cache-quota':
            StaticSetter(
                getter=QWebSettings.offlineWebApplicationCacheQuota,
                setter=QWebSettings.setOfflineWebApplicationCacheQuota),
    },
    'general': {
        'private-browsing':
            Attribute(QWebSettings.PrivateBrowsingEnabled),
        'developer-extras':
            Attribute(QWebSettings.DeveloperExtrasEnabled),
        'print-element-backgrounds':
            Attribute(QWebSettings.PrintElementBackgrounds),
        'xss-auditing':
            Attribute(QWebSettings.XSSAuditingEnabled),
        'site-specific-quirks':
            Attribute(QWebSettings.SiteSpecificQuirksEnabled),
        'default-encoding':
            Setter(getter=QWebSettings.defaultTextEncoding,
                   setter=QWebSettings.setDefaultTextEncoding),
    }
}
