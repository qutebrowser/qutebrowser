# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import typing
import os.path

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QFont
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebPage

from qutebrowser.config import config, websettings
from qutebrowser.config.websettings import AttributeInfo as Attr
from qutebrowser.utils import standarddir, urlutils
from qutebrowser.browser import shared


# The global WebKitSettings object
global_settings = typing.cast('WebKitSettings', None)

parsed_user_agent = None


class WebKitSettings(websettings.AbstractSettings):

    """A wrapper for the config for QWebSettings."""

    _ATTRIBUTES = {
        'content.images':
            Attr(QWebSettings.AutoLoadImages),
        'content.javascript.enabled':
            Attr(QWebSettings.JavascriptEnabled),
        'content.javascript.can_open_tabs_automatically':
            Attr(QWebSettings.JavascriptCanOpenWindows),
        'content.javascript.can_close_tabs':
            Attr(QWebSettings.JavascriptCanCloseWindows),
        'content.javascript.can_access_clipboard':
            Attr(QWebSettings.JavascriptCanAccessClipboard),
        'content.plugins':
            Attr(QWebSettings.PluginsEnabled),
        'content.webgl':
            Attr(QWebSettings.WebGLEnabled),
        'content.hyperlink_auditing':
            Attr(QWebSettings.HyperlinkAuditingEnabled),
        'content.local_content_can_access_remote_urls':
            Attr(QWebSettings.LocalContentCanAccessRemoteUrls),
        'content.local_content_can_access_file_urls':
            Attr(QWebSettings.LocalContentCanAccessFileUrls),
        'content.dns_prefetch':
            Attr(QWebSettings.DnsPrefetchEnabled),
        'content.frame_flattening':
            Attr(QWebSettings.FrameFlatteningEnabled),
        'content.cache.appcache':
            Attr(QWebSettings.OfflineWebApplicationCacheEnabled),
        'content.local_storage':
            Attr(QWebSettings.LocalStorageEnabled,
                 QWebSettings.OfflineStorageDatabaseEnabled),
        'content.print_element_backgrounds':
            Attr(QWebSettings.PrintElementBackgrounds),
        'content.xss_auditing':
            Attr(QWebSettings.XSSAuditingEnabled),
        'content.site_specific_quirks':
            Attr(QWebSettings.SiteSpecificQuirksEnabled),

        'input.spatial_navigation':
            Attr(QWebSettings.SpatialNavigationEnabled),
        'input.links_included_in_focus_chain':
            Attr(QWebSettings.LinksIncludedInFocusChain),

        'zoom.text_only':
            Attr(QWebSettings.ZoomTextOnly),
        'scrolling.smooth':
            Attr(QWebSettings.ScrollAnimatorEnabled),
    }

    _FONT_SIZES = {
        'fonts.web.size.minimum':
            QWebSettings.MinimumFontSize,
        'fonts.web.size.minimum_logical':
            QWebSettings.MinimumLogicalFontSize,
        'fonts.web.size.default':
            QWebSettings.DefaultFontSize,
        'fonts.web.size.default_fixed':
            QWebSettings.DefaultFixedFontSize,
    }

    _FONT_FAMILIES = {
        'fonts.web.family.standard': QWebSettings.StandardFont,
        'fonts.web.family.fixed': QWebSettings.FixedFont,
        'fonts.web.family.serif': QWebSettings.SerifFont,
        'fonts.web.family.sans_serif': QWebSettings.SansSerifFont,
        'fonts.web.family.cursive': QWebSettings.CursiveFont,
        'fonts.web.family.fantasy': QWebSettings.FantasyFont,
    }

    # Mapping from QWebSettings::QWebSettings() in
    # qtwebkit/Source/WebKit/qt/Api/qwebsettings.cpp
    _FONT_TO_QFONT = {
        QWebSettings.StandardFont: QFont.Serif,
        QWebSettings.FixedFont: QFont.Monospace,
        QWebSettings.SerifFont: QFont.Serif,
        QWebSettings.SansSerifFont: QFont.SansSerif,
        QWebSettings.CursiveFont: QFont.Cursive,
        QWebSettings.FantasyFont: QFont.Fantasy,
    }


def _set_user_stylesheet(settings):
    """Set the generated user-stylesheet."""
    stylesheet = shared.get_user_stylesheet().encode('utf-8')
    url = urlutils.data_url('text/css;charset=utf-8', stylesheet)
    settings.setUserStyleSheetUrl(url)


def _set_cookie_accept_policy(settings):
    """Update the content.cookies.accept setting."""
    mapping = {
        'all': QWebSettings.AlwaysAllowThirdPartyCookies,
        'no-3rdparty': QWebSettings.AlwaysBlockThirdPartyCookies,
        'never': QWebSettings.AlwaysBlockThirdPartyCookies,
        'no-unknown-3rdparty': QWebSettings.AllowThirdPartyWithExistingCookies,
    }
    value = config.val.content.cookies.accept
    settings.setThirdPartyCookiePolicy(mapping[value])


def _set_cache_maximum_pages(settings):
    """Update the content.cache.maximum_pages setting."""
    value = config.val.content.cache.maximum_pages
    settings.setMaximumPagesInCache(value)


def _update_settings(option):
    """Update global settings when qwebsettings changed."""
    global_settings.update_setting(option)

    settings = QWebSettings.globalSettings()
    if option in ['scrollbar.hide', 'content.user_stylesheets']:
        _set_user_stylesheet(settings)
    elif option == 'content.cookies.accept':
        _set_cookie_accept_policy(settings)
    elif option == 'content.cache.maximum_pages':
        _set_cache_maximum_pages(settings)


def _init_user_agent():
    global parsed_user_agent
    ua = QWebPage().userAgentForUrl(QUrl())
    parsed_user_agent = websettings.UserAgent.parse(ua)


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

    settings = QWebSettings.globalSettings()
    _set_user_stylesheet(settings)
    _set_cookie_accept_policy(settings)
    _set_cache_maximum_pages(settings)

    _init_user_agent()

    config.instance.changed.connect(_update_settings)

    global global_settings
    global_settings = WebKitSettings(QWebSettings.globalSettings())
    global_settings.init_settings()


def shutdown():
    """Disable storage so removing tmpdir will work."""
    QWebSettings.setIconDatabasePath('')
    QWebSettings.setOfflineWebApplicationCachePath('')
    QWebSettings.globalSettings().setLocalStoragePath('')
