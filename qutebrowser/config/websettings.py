# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os.path

from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtCore import QStandardPaths, QUrl

from qutebrowser.config import config
from qutebrowser.utils import usertypes, standarddir, objreg

MapType = usertypes.enum('MapType', ['attribute', 'setter', 'static_setter'])


MAPPINGS = {
    'content': {
        'allow-images':
            (MapType.attribute, QWebSettings.AutoLoadImages),
        'allow-javascript':
            (MapType.attribute, QWebSettings.JavascriptEnabled),
        'javascript-can-open-windows':
            (MapType.attribute, QWebSettings.JavascriptCanOpenWindows),
        'javascript-can-close-windows':
            (MapType.attribute, QWebSettings.JavascriptCanCloseWindows),
        'javascript-can-access-clipboard':
            (MapType.attribute, QWebSettings.JavascriptCanAccessClipboard),
        #'allow-java':
        #   (MapType.attribute, QWebSettings.JavaEnabled),
        'allow-plugins':
            (MapType.attribute, QWebSettings.PluginsEnabled),
        'local-content-can-access-remote-urls':
            (MapType.attribute, QWebSettings.LocalContentCanAccessRemoteUrls),
        'local-content-can-access-file-urls':
            (MapType.attribute, QWebSettings.LocalContentCanAccessFileUrls),
    },
    'network': {
        'dns-prefetch':
            (MapType.attribute, QWebSettings.DnsPrefetchEnabled),
    },
    'input': {
        'spatial-navigation':
            (MapType.attribute, QWebSettings.SpatialNavigationEnabled),
        'links-included-in-focus-chain':
            (MapType.attribute, QWebSettings.LinksIncludedInFocusChain),
    },
    'fonts': {
        'web-family-standard':
            (MapType.setter, lambda qws, v:
             qws.setFontFamily(QWebSettings.StandardFont, v),
             ""),
        'web-family-fixed':
            (MapType.setter, lambda qws, v:
             qws.setFontFamily(QWebSettings.FixedFont, v),
             ""),
        'web-family-serif':
            (MapType.setter, lambda qws, v:
             qws.setFontFamily(QWebSettings.SerifFont, v),
             ""),
        'web-family-sans-serif':
            (MapType.setter, lambda qws, v:
             qws.setFontFamily(QWebSettings.SansSerifFont, v),
             ""),
        'web-family-cursive':
            (MapType.setter, lambda qws, v:
             qws.setFontFamily(QWebSettings.CursiveFont, v),
             ""),
        'web-family-fantasy':
            (MapType.setter, lambda qws, v:
             qws.setFontFamily(QWebSettings.FantasyFont, v),
             ""),
        'web-size-minimum':
            (MapType.setter, lambda qws, v:
             qws.setFontSize(QWebSettings.MinimumFontSize, v)),
        'web-size-minimum-logical':
            (MapType.setter, lambda qws, v:
             qws.setFontSize(QWebSettings.MinimumLogicalFontSize, v)),
        'web-size-default':
            (MapType.setter, lambda qws, v:
             qws.setFontSize(QWebSettings.DefaultFontSize, v)),
        'web-size-default-fixed':
            (MapType.setter, lambda qws, v:
             qws.setFontSize(QWebSettings.DefaultFixedFontSize, v)),
    },
    'ui': {
        'zoom-text-only':
            (MapType.attribute, QWebSettings.ZoomTextOnly),
        'frame-flattening':
            (MapType.attribute, QWebSettings.FrameFlatteningEnabled),
        'user-stylesheet':
            (MapType.setter, lambda qws, v:
             qws.setUserStyleSheetUrl(v),
             QUrl()),
        'css-media-type':
            (MapType.setter, lambda qws, v:
             qws.setCSSMediaType(v)),
        #'accelerated-compositing':
        #   (MapType.attribute, QWebSettings.AcceleratedCompositingEnabled),
        #'tiled-backing-store':
        #   (MapType.attribute, QWebSettings.TiledBackingStoreEnabled),
    },
    'storage': {
        'offline-storage-database':
            (MapType.attribute, QWebSettings.OfflineStorageDatabaseEnabled),
        'offline-web-application-storage':
            (MapType.attribute,
             QWebSettings.OfflineWebApplicationCacheEnabled),
        'local-storage':
            (MapType.attribute, QWebSettings.LocalStorageEnabled),
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
    },
    'general': {
        'private-browsing':
            (MapType.attribute, QWebSettings.PrivateBrowsingEnabled),
        'developer-extras':
            (MapType.attribute, QWebSettings.DeveloperExtrasEnabled),
        'print-element-backgrounds':
            (MapType.attribute, QWebSettings.PrintElementBackgrounds),
        'xss-auditing':
            (MapType.attribute, QWebSettings.XSSAuditingEnabled),
        'site-specific-quirks':
            (MapType.attribute, QWebSettings.SiteSpecificQuirksEnabled),
        'default-encoding':
            (MapType.setter, lambda qws, v: qws.setDefaultTextEncoding(v), ""),
    }
}


settings = None
UNSET = object()


def _set_setting(typ, arg, default=UNSET, value=UNSET):
    """Set a QWebSettings setting.

    Args:
        typ: The type of the item.
        arg: The argument (attribute/handler)
        default: The value to use if the user set an empty string.
        value: The value to set.
    """
    if not isinstance(typ, MapType):
        raise TypeError("Type {} is no MapType member!".format(typ))
    if value is UNSET:
        raise TypeError("No value given!")
    if value is None:
        if default is UNSET:
            return
        else:
            value = default

    if typ == MapType.attribute:
        settings.setAttribute(arg, value)
    elif typ == MapType.setter:
        arg(settings, value)
    elif typ == MapType.static_setter:
        arg(value)


def init():
    """Initialize the global QWebSettings."""
    cachedir = standarddir.get(QStandardPaths.CacheLocation)
    QWebSettings.setIconDatabasePath(cachedir)
    QWebSettings.setOfflineWebApplicationCachePath(
        os.path.join(cachedir, 'application-cache'))
    datadir = standarddir.get(QStandardPaths.DataLocation)
    QWebSettings.globalSettings().setLocalStoragePath(
        os.path.join(datadir, 'local-storage'))
    QWebSettings.setOfflineStoragePath(
        os.path.join(datadir, 'offline-storage'))

    global settings
    settings = QWebSettings.globalSettings()
    for sectname, section in MAPPINGS.items():
        for optname, mapping in section.items():
            value = config.get(sectname, optname)
            _set_setting(*mapping, value=value)
    objreg.get('config').changed.connect(update_settings)


def update_settings(section, option):
    """Update global settings when qwebsettings changed."""
    try:
        mapping = MAPPINGS[section][option]
    except KeyError:
        return
    value = config.get(section, option)
    _set_setting(*mapping, value=value)
