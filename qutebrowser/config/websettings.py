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
from PyQt5.QtCore import QStandardPaths

import qutebrowser.config.config as config
from qutebrowser.utils.usertypes import enum
from qutebrowser.utils.misc import get_standard_dir

MapType = enum('attribute', 'setter', 'static_setter')


MAPPINGS = {
    # noqa
    'auto-load-images':
        (MapType.attribute, QWebSettings.AutoLoadImages),
    'dns-prefetch-enabled':
        (MapType.attribute, QWebSettings.DnsPrefetchEnabled),
    'javascript-enabled':
        (MapType.attribute, QWebSettings.JavascriptEnabled),
    #'java-enabled':
    #   (MapType.attribute, QWebSettings.JavaEnabled),
    'plugins-enabled':
        (MapType.attribute, QWebSettings.PluginsEnabled),
    'private-browsing-enabled':
        (MapType.attribute, QWebSettings.PrivateBrowsingEnabled),
    'javascript-can-open-windows':
        (MapType.attribute, QWebSettings.JavascriptCanOpenWindows),
    'javascript-can-close-windows':
        (MapType.attribute, QWebSettings.JavascriptCanCloseWindows),
    'javascript-can-access-clipboard':
        (MapType.attribute, QWebSettings.JavascriptCanAccessClipboard),
    'developer-extras-enabled':
        (MapType.attribute, QWebSettings.DeveloperExtrasEnabled),
    'spatial-navigation-enabled':
        (MapType.attribute, QWebSettings.SpatialNavigationEnabled),
    'links-included-in-focus-chain':
        (MapType.attribute, QWebSettings.LinksIncludedInFocusChain),
    'zoom-text-only':
        (MapType.attribute, QWebSettings.ZoomTextOnly),
    'print-element-backgrounds':
        (MapType.attribute, QWebSettings.PrintElementBackgrounds),
    'offline-storage-database-enabled':
        (MapType.attribute, QWebSettings.OfflineStorageDatabaseEnabled),
    'offline-web-application-storage-enabled':
        (MapType.attribute, QWebSettings.OfflineWebApplicationCacheEnabled),
    'local-storage-enabled':
        (MapType.attribute, QWebSettings.LocalStorageEnabled),
    'local-content-can-access-remote-urls':
        (MapType.attribute, QWebSettings.LocalContentCanAccessRemoteUrls),
    'local-content-can-access-file-urls':
        (MapType.attribute, QWebSettings.LocalContentCanAccessFileUrls),
    'xss-auditing-enabled':
        (MapType.attribute, QWebSettings.XSSAuditingEnabled),
    #'accelerated-compositing-enabled':
    #   (MapType.attribute, QWebSettings.AcceleratedCompositingEnabled),
    #'tiled-backing-store-enabled':
    #   (MapType.attribute, QWebSettings.TiledBackingStoreEnabled),
    'frame-flattening-enabled':
        (MapType.attribute, QWebSettings.FrameFlatteningEnabled),
    'site-specific-quirks-enabled':
        (MapType.attribute, QWebSettings.SiteSpecificQuirksEnabled),
    'user-stylesheet':
        (MapType.setter, lambda qws, v: qws.setUserStyleSheetUrl(v)),
    'css-media-type':
        (MapType.setter, lambda qws, v: qws.setCSSMediaType(v)),
    'default-encoding':
        (MapType.setter, lambda qws, v: qws.setDefaultTextEncoding(v)),
    'font-family-standard':
        (MapType.setter, lambda qws, v:
            qws.setFontFamily(QWebSettings.StandardFont, v)),
    'font-family-fixed':
        (MapType.setter, lambda qws, v:
            qws.setFontFamily(QWebSettings.FixedFont, v)),
    'font-family-serif':
        (MapType.setter, lambda qws, v:
            qws.setFontFamily(QWebSettings.SerifFont, v)),
    'font-family-sans-serif':
        (MapType.setter, lambda qws, v:
            qws.setFontFamily(QWebSettings.SansSerifFont, v)),
    'font-family-cursive':
        (MapType.setter, lambda qws, v:
            qws.setFontFamily(QWebSettings.CursiveFont, v)),
    'font-family-fantasy':
        (MapType.setter, lambda qws, v:
            qws.setFontFamily(QWebSettings.FantasyFont, v)),
    'maximum-pages-in-cache':
        (MapType.static_setter, lambda v:
            QWebSettings.setMaximumPagesInCache(v)),
    'object-cache-capacities':
        (MapType.static_setter, lambda v:
            QWebSettings.setObjectCacheCapacities(*v)),
    'offline-storage-default-quota':
        (MapType.static_setter, lambda v:
            QWebSettings.setOfflineStorageDefaultQuota(v)),
    'offline-web-application-cache-quota':
        (MapType.static_setter, lambda v:
            QWebSettings.setOfflineWebApplicationCacheQuota(v)),
}


settings = None


def _set_setting(typ, arg, value):
    """Set a QWebSettings setting.

    Args:
        typ: The type of the item
             (MapType.attribute/MapType.setter/MapType.static_setter)
        arg: The argument (attribute/handler)
        value: The value to set.
    """
    if typ == MapType.attribute:
        settings.setAttribute(arg, value)
    elif typ == MapType.setter and value is not None:
        arg(settings, value)
    elif typ == MapType.static_setter and value is not None:
        arg(value)


def init():
    """Initialize the global QWebSettings."""
    global settings
    cachedir = get_standard_dir(QStandardPaths.CacheLocation)
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
