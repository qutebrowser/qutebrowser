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


ATTRIBUTES = {
    # noqa
    'auto-load-images': QWebSettings.AutoLoadImages,
    'dns-prefetch-enabled': QWebSettings.DnsPrefetchEnabled,
    'javascript-enabled': QWebSettings.JavascriptEnabled,
    #'java-enabled': #QWebSettings.JavaEnabled,
    'plugins-enabled': QWebSettings.PluginsEnabled,
    'private-browsing-enabled': QWebSettings.PrivateBrowsingEnabled,
    'javascript-can-open-windows': QWebSettings.JavascriptCanOpenWindows,
    'javascript-can-close-windows': QWebSettings.JavascriptCanCloseWindows,
    'javascript-can-access-clipboard':
        QWebSettings.JavascriptCanAccessClipboard,
    'developer-extras-enabled': QWebSettings.DeveloperExtrasEnabled,
    'spatial-navigation-enabled': QWebSettings.SpatialNavigationEnabled,
    'links-included-in-focus-chain': QWebSettings.LinksIncludedInFocusChain,
    'zoom-text-only': QWebSettings.ZoomTextOnly,
    'print-element-backgrounds': QWebSettings.PrintElementBackgrounds,
    'offline-storage-database-enabled':
        QWebSettings.OfflineStorageDatabaseEnabled,
    'offline-web-application-storage-enabled':
        QWebSettings.OfflineWebApplicationCacheEnabled,
    'local-storage-enabled': QWebSettings.LocalStorageEnabled,
    'local-content-can-access-remote-urls':
        QWebSettings.LocalContentCanAccessRemoteUrls,
    'local-content-can-access-file-urls':
        QWebSettings.LocalContentCanAccessFileUrls,
    'xss-auditing-enabled': QWebSettings.XSSAuditingEnabled,
    #'accelerated-compositing-enabled':
    #   QWebSettings.AcceleratedCompositingEnabled,
    #'tiled-backing-store-enabled': QWebSettings.TiledBackingStoreEnabled,
    'frame-flattening-enabled': QWebSettings.FrameFlatteningEnabled,
    'site-specific-quirks-enabled': QWebSettings.SiteSpecificQuirksEnabled,
}


SETTERS = {
    'user-stylesheet':
        lambda qws, v: qws.setUserStyleSheetUrl(v),
    'css-media-type':
        lambda qws, v: qws.setCSSMediaType(v),
    'default-encoding':
        lambda qws, v: qws.setDefaultTextEncoding(v),
    'font-family-standard':
        lambda qws, v: qws.setFontFamily(QWebSettings.StandardFont, v),
    'font-family-fixed':
        lambda qws, v: qws.setFontFamily(QWebSettings.FixedFont, v),
    'font-family-serif':
        lambda qws, v: qws.setFontFamily(QWebSettings.SerifFont, v),
    'font-family-sans-serif':
        lambda qws, v: qws.setFontFamily(QWebSettings.SansSerifFont, v),
    'font-family-cursive':
        lambda qws, v: qws.setFontFamily(QWebSettings.CursiveFont, v),
    'font-family-fantasy':
        lambda qws, v: qws.setFontFamily(QWebSettings.FantasyFont, v),
}


STATIC_SETTERS = {
    'maximum-pages-in-cache':
        lambda v: QWebSettings.setMaximumPagesInCache(v),
    'object-cache-capacities':
        lambda v: QWebSettings.setObjectCacheCapacities(*v),
    'offline-storage-default-quota':
        lambda v: QWebSettings.setOfflineStorageDefaultQuota(v),
    'offline-web-application-cache-quota':
        lambda v: QWebSettings.setOfflineWebApplicationCacheQuota(v),
}


settings = None


def init(cachedir):
    """Initialize the global QWebSettings.

    Args:
        cachedir: Directory to save cache files in.
    """
    global settings
    QWebSettings.enablePersistentStorage(cachedir)
    settings = QWebSettings.globalSettings()
    for name, item in ATTRIBUTES.items():
        settings.setAttribute(item, config.get('webkit', name))
    for name, setter in SETTERS.items():
        value = config.get('webkit', name)
        if value is not None:
            setter(settings, value)
    for name, setter in STATIC_SETTERS.items():
        value = config.get('webkit', name)
        if value is not None:
            setter(value)


@pyqtSlot(str, str)
def on_config_changed(section, option):
    """Update global settings when qwebsettings changed."""
    if section == 'webkit':
        value = config.get(section, option)
        if option in ATTRIBUTES:
            settings.setAttribute(ATTRIBUTES[option], value)
        elif option in SETTERS and value is not None:
            SETTERS[option](settings, value)
        elif option in STATIC_SETTERS and value is not None:
            STATIC_SETTERS[option](value)
