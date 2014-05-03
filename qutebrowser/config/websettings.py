# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
    SETTERS: A mapping from setting names to QWebSetting setter method names.
    settings: The global QWebSettings singleton instance.
"""

# pylint: disable=unnecessary-lambda

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWebKit import QWebSettings

import qutebrowser.config.config as config

ATTRIBUTE = 0
SETTER = 1
STATIC_SETTER = 2


MAPPINGS = {
    # noqa
    'auto-load-images':
        (ATTRIBUTE, QWebSettings.AutoLoadImages),
    'dns-prefetch-enabled':
        (ATTRIBUTE, QWebSettings.DnsPrefetchEnabled),
    'javascript-enabled':
        (ATTRIBUTE, QWebSettings.JavascriptEnabled),
    #'java-enabled':
    #   (ATTRIBUTE, QWebSettings.JavaEnabled),
    'plugins-enabled':
        (ATTRIBUTE, QWebSettings.PluginsEnabled),
    'private-browsing-enabled':
        (ATTRIBUTE, QWebSettings.PrivateBrowsingEnabled),
    'javascript-can-open-windows':
        (ATTRIBUTE, QWebSettings.JavascriptCanOpenWindows),
    'javascript-can-close-windows':
        (ATTRIBUTE, QWebSettings.JavascriptCanCloseWindows),
    'javascript-can-access-clipboard':
        (ATTRIBUTE, QWebSettings.JavascriptCanAccessClipboard),
    'developer-extras-enabled':
        (ATTRIBUTE, QWebSettings.DeveloperExtrasEnabled),
    'spatial-navigation-enabled':
        (ATTRIBUTE, QWebSettings.SpatialNavigationEnabled),
    'links-included-in-focus-chain':
        (ATTRIBUTE, QWebSettings.LinksIncludedInFocusChain),
    'zoom-text-only':
        (ATTRIBUTE, QWebSettings.ZoomTextOnly),
    'print-element-backgrounds':
        (ATTRIBUTE, QWebSettings.PrintElementBackgrounds),
    'offline-storage-database-enabled':
        (ATTRIBUTE, QWebSettings.OfflineStorageDatabaseEnabled),
    'offline-web-application-storage-enabled':
        (ATTRIBUTE, QWebSettings.OfflineWebApplicationCacheEnabled),
    'local-storage-enabled':
        (ATTRIBUTE, QWebSettings.LocalStorageEnabled),
    'local-content-can-access-remote-urls':
        (ATTRIBUTE, QWebSettings.LocalContentCanAccessRemoteUrls),
    'local-content-can-access-file-urls':
        (ATTRIBUTE, QWebSettings.LocalContentCanAccessFileUrls),
    'xss-auditing-enabled':
        (ATTRIBUTE, QWebSettings.XSSAuditingEnabled),
    #'accelerated-compositing-enabled':
    #   (ATTRIBUTE, QWebSettings.AcceleratedCompositingEnabled),
    #'tiled-backing-store-enabled':
    #   (ATTRIBUTE, QWebSettings.TiledBackingStoreEnabled),
    'frame-flattening-enabled':
        (ATTRIBUTE, QWebSettings.FrameFlatteningEnabled),
    'site-specific-quirks-enabled':
        (ATTRIBUTE, QWebSettings.SiteSpecificQuirksEnabled),
    'user-stylesheet':
        (SETTER, lambda qws, v: qws.setUserStyleSheetUrl(v)),
    'css-media-type':
        (SETTER, lambda qws, v: qws.setCSSMediaType(v)),
    'default-encoding':
        (SETTER, lambda qws, v: qws.setDefaultTextEncoding(v)),
    'font-family-standard':
        (SETTER, lambda qws, v:
            qws.setFontFamily(QWebSettings.StandardFont, v)),
    'font-family-fixed':
        (SETTER, lambda qws, v:
            qws.setFontFamily(QWebSettings.FixedFont, v)),
    'font-family-serif':
        (SETTER, lambda qws, v:
            qws.setFontFamily(QWebSettings.SerifFont, v)),
    'font-family-sans-serif':
        (SETTER, lambda qws, v:
            qws.setFontFamily(QWebSettings.SansSerifFont, v)),
    'font-family-cursive':
        (SETTER, lambda qws, v:
            qws.setFontFamily(QWebSettings.CursiveFont, v)),
    'font-family-fantasy':
        (SETTER, lambda qws, v:
            qws.setFontFamily(QWebSettings.FantasyFont, v)),
    'maximum-pages-in-cache':
        (STATIC_SETTER, lambda v: QWebSettings.setMaximumPagesInCache(v)),
    'object-cache-capacities':
        (STATIC_SETTER, lambda v: QWebSettings.setObjectCacheCapacities(*v)),
    'offline-storage-default-quota':
        (STATIC_SETTER, lambda v:
            QWebSettings.setOfflineStorageDefaultQuota(v)),
    'offline-web-application-cache-quota':
        (STATIC_SETTER, lambda v:
            QWebSettings.setOfflineWebApplicationCacheQuota(v)),
}


settings = None


def _set_setting(typ, arg, value):
    """Set a QWebSettings setting.

    Args:
        typ: The type of the item (ATTRIBUTE/SETTER/STATIC_SETTER)
        arg: The argument (attribute/handler)
        value: The value to set.
    """
    if typ == ATTRIBUTE:
        settings.setAttribute(arg, value)
    elif typ == SETTER and value is not None:
        arg(settings, value)
    elif typ == STATIC_SETTER and value is not None:
        arg(value)


def init(cachedir):
    """Initialize the global QWebSettings.

    Args:
        cachedir: Directory to save cache files in.
    """
    global settings
    QWebSettings.enablePersistentStorage(cachedir)
    settings = QWebSettings.globalSettings()
    for name, (typ, arg) in MAPPINGS.items():
        value = config.get('webkit', name)
        _set_setting(typ, arg, value)


@pyqtSlot(str, str)
def on_config_changed(section, option):
    """Update global settings when qwebsettings changed."""
    if section == 'webkit':
        value = config.get(section, option)
        typ, arg = MAPPINGS[option]
        _set_setting(typ, arg, value)
