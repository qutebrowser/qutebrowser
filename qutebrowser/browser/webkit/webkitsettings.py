# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Bridge from QWebSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebSetting enum
                constants.
"""

from typing import cast
import os.path

from qutebrowser.qt import QtWebKitWidgets, QtWebKit, QtGui, QtCore

from qutebrowser.config import config, websettings
from qutebrowser.config.websettings import AttributeInfo as Attr
from qutebrowser.utils import standarddir, urlutils
from qutebrowser.browser import shared


# The global WebKitSettings object
global_settings = cast('WebKitSettings', None)

parsed_user_agent = None


class WebKitSettings(websettings.AbstractSettings):

    """A wrapper for the config for QWebSettings."""

    _ATTRIBUTES = {
        'content.images':
            Attr(QtWebKit.QWebSettings.AutoLoadImages),
        'content.javascript.enabled':
            Attr(QtWebKit.QWebSettings.JavascriptEnabled),
        'content.javascript.can_open_tabs_automatically':
            Attr(QtWebKit.QWebSettings.JavascriptCanOpenWindows),
        'content.javascript.can_close_tabs':
            Attr(QtWebKit.QWebSettings.JavascriptCanCloseWindows),
        'content.javascript.can_access_clipboard':
            Attr(QtWebKit.QWebSettings.JavascriptCanAccessClipboard),
        'content.plugins':
            Attr(QtWebKit.QWebSettings.PluginsEnabled),
        'content.webgl':
            Attr(QtWebKit.QWebSettings.WebGLEnabled),
        'content.hyperlink_auditing':
            Attr(QtWebKit.QWebSettings.HyperlinkAuditingEnabled),
        'content.local_content_can_access_remote_urls':
            Attr(QtWebKit.QWebSettings.LocalContentCanAccessRemoteUrls),
        'content.local_content_can_access_file_urls':
            Attr(QtWebKit.QWebSettings.LocalContentCanAccessFileUrls),
        'content.dns_prefetch':
            Attr(QtWebKit.QWebSettings.DnsPrefetchEnabled),
        'content.frame_flattening':
            Attr(QtWebKit.QWebSettings.FrameFlatteningEnabled),
        'content.cache.appcache':
            Attr(QtWebKit.QWebSettings.OfflineWebApplicationCacheEnabled),
        'content.local_storage':
            Attr(QtWebKit.QWebSettings.LocalStorageEnabled,
                 QtWebKit.QWebSettings.OfflineStorageDatabaseEnabled),
        'content.print_element_backgrounds':
            Attr(QtWebKit.QWebSettings.PrintElementBackgrounds),
        'content.xss_auditing':
            Attr(QtWebKit.QWebSettings.XSSAuditingEnabled),
        'content.site_specific_quirks.enabled':
            Attr(QtWebKit.QWebSettings.SiteSpecificQuirksEnabled),

        'input.spatial_navigation':
            Attr(QtWebKit.QWebSettings.SpatialNavigationEnabled),
        'input.links_included_in_focus_chain':
            Attr(QtWebKit.QWebSettings.LinksIncludedInFocusChain),

        'zoom.text_only':
            Attr(QtWebKit.QWebSettings.ZoomTextOnly),
        'scrolling.smooth':
            Attr(QtWebKit.QWebSettings.ScrollAnimatorEnabled),
    }

    _FONT_SIZES = {
        'fonts.web.size.minimum':
            QtWebKit.QWebSettings.MinimumFontSize,
        'fonts.web.size.minimum_logical':
            QtWebKit.QWebSettings.MinimumLogicalFontSize,
        'fonts.web.size.default':
            QtWebKit.QWebSettings.DefaultFontSize,
        'fonts.web.size.default_fixed':
            QtWebKit.QWebSettings.DefaultFixedFontSize,
    }

    _FONT_FAMILIES = {
        'fonts.web.family.standard': QtWebKit.QWebSettings.StandardFont,
        'fonts.web.family.fixed': QtWebKit.QWebSettings.FixedFont,
        'fonts.web.family.serif': QtWebKit.QWebSettings.SerifFont,
        'fonts.web.family.sans_serif': QtWebKit.QWebSettings.SansSerifFont,
        'fonts.web.family.cursive': QtWebKit.QWebSettings.CursiveFont,
        'fonts.web.family.fantasy': QtWebKit.QWebSettings.FantasyFont,
    }

    # Mapping from QWebSettings::QWebSettings() in
    # qtwebkit/Source/WebKit/qt/Api/qwebsettings.cpp
    _FONT_TO_QFONT = {
        QtWebKit.QWebSettings.StandardFont: QtGui.QFont.Serif,
        QtWebKit.QWebSettings.FixedFont: QtGui.QFont.Monospace,
        QtWebKit.QWebSettings.SerifFont: QtGui.QFont.Serif,
        QtWebKit.QWebSettings.SansSerifFont: QtGui.QFont.SansSerif,
        QtWebKit.QWebSettings.CursiveFont: QtGui.QFont.Cursive,
        QtWebKit.QWebSettings.FantasyFont: QtGui.QFont.Fantasy,
    }


def _set_user_stylesheet(settings):
    """Set the generated user-stylesheet."""
    stylesheet = shared.get_user_stylesheet().encode('utf-8')
    url = urlutils.data_url('text/css;charset=utf-8', stylesheet)
    settings.setUserStyleSheetUrl(url)


def _set_cookie_accept_policy(settings):
    """Update the content.cookies.accept setting."""
    mapping = {
        'all': QtWebKit.QWebSettings.AlwaysAllowThirdPartyCookies,
        'no-3rdparty': QtWebKit.QWebSettings.AlwaysBlockThirdPartyCookies,
        'never': QtWebKit.QWebSettings.AlwaysBlockThirdPartyCookies,
        'no-unknown-3rdparty': QtWebKit.QWebSettings.AllowThirdPartyWithExistingCookies,
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

    settings = QtWebKit.QWebSettings.globalSettings()
    if option in ['scrollbar.hide', 'content.user_stylesheets']:
        _set_user_stylesheet(settings)
    elif option == 'content.cookies.accept':
        _set_cookie_accept_policy(settings)
    elif option == 'content.cache.maximum_pages':
        _set_cache_maximum_pages(settings)


def _init_user_agent():
    global parsed_user_agent
    ua = QtWebKitWidgets.QWebPage().userAgentForUrl(QtCore.QUrl())
    parsed_user_agent = websettings.UserAgent.parse(ua)


def init():
    """Initialize the global QWebSettings."""
    cache_path = standarddir.cache()
    data_path = standarddir.data()

    QtWebKit.QWebSettings.setIconDatabasePath(standarddir.cache())
    QtWebKit.QWebSettings.setOfflineWebApplicationCachePath(
        os.path.join(cache_path, 'application-cache'))
    QtWebKit.QWebSettings.globalSettings().setLocalStoragePath(
        os.path.join(data_path, 'local-storage'))
    QtWebKit.QWebSettings.setOfflineStoragePath(
        os.path.join(data_path, 'offline-storage'))

    settings = QtWebKit.QWebSettings.globalSettings()
    _set_user_stylesheet(settings)
    _set_cookie_accept_policy(settings)
    _set_cache_maximum_pages(settings)

    _init_user_agent()

    config.instance.changed.connect(_update_settings)

    global global_settings
    global_settings = WebKitSettings(QtWebKit.QWebSettings.globalSettings())
    global_settings.init_settings()


def shutdown():
    """Disable storage so removing tmpdir will work."""
    QtWebKit.QWebSettings.setIconDatabasePath('')
    QtWebKit.QWebSettings.setOfflineWebApplicationCachePath('')
    QtWebKit.QWebSettings.globalSettings().setLocalStoragePath('')
