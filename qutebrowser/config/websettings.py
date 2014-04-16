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

"""Bridge from QWebSettings to our own settings."""

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWebKit import QWebSettings

import qutebrowser.config.config as config


MAPPING = {
    # noqa
    'auto_load_images': QWebSettings.AutoLoadImages,
    'dns_prefetch_enabled': QWebSettings.DnsPrefetchEnabled,
    'javascript_enabled': QWebSettings.JavascriptEnabled,
    #'java_enabled': #QWebSettings.JavaEnabled,
    'plugins_enabled': QWebSettings.PluginsEnabled,
    'private_browsing_enabled': QWebSettings.PrivateBrowsingEnabled,
    'javascript_can_open_windows': QWebSettings.JavascriptCanOpenWindows,
    'javascript_can_close_windows': QWebSettings.JavascriptCanCloseWindows,
    'javascript_can_access_clipboard':
        QWebSettings.JavascriptCanAccessClipboard,
    'developer_extras_enabled': QWebSettings.DeveloperExtrasEnabled,
    'spatial_navigation_enabled': QWebSettings.SpatialNavigationEnabled,
    'links_included_in_focus_chain': QWebSettings.LinksIncludedInFocusChain,
    'zoom_text_only': QWebSettings.ZoomTextOnly,
    'print_element_backgrounds': QWebSettings.PrintElementBackgrounds,
    'offline_storage_database_enabled':
        QWebSettings.OfflineStorageDatabaseEnabled,
    'offline_web_application_storage_enabled':
        QWebSettings.OfflineWebApplicationCacheEnabled,
    'local_storage_enabled': QWebSettings.LocalStorageEnabled,
    'local_content_can_access_remote_urls':
        QWebSettings.LocalContentCanAccessRemoteUrls,
    'local_content_can_access_file_urls':
        QWebSettings.LocalContentCanAccessFileUrls,
    'xss_auditing_enabled': QWebSettings.XSSAuditingEnabled,
    #'accelerated_compositing_enabled':
    #   QWebSettings.AcceleratedCompositingEnabled,
    #'tiled_backing_store_enabled': QWebSettings.TiledBackingStoreEnabled,
    'frame_flattening_enabled': QWebSettings.FrameFlatteningEnabled,
    'site_specific_quirks_enabled': QWebSettings.SiteSpecificQuirksEnabled,
}

settings = None


def init():
    """Initialize the global QWebSettings."""
    global settings
    settings = QWebSettings.globalSettings()
    for name, item in MAPPING.items():
        settings.setAttribute(item, config.config.get('webkit', name))


@pyqtSlot(str, str, object)
def on_config_changed(section, option, value):
    """Update global settings when qwebsettings changed."""
    if section == 'webkit':
        settings.setAttribute(MAPPING[option], value)
