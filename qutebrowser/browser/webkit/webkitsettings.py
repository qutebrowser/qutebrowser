# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bridge from QWebSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebSetting enum
                constants.
"""

from typing import cast
import os.path

from qutebrowser.qt.core import QUrl
from qutebrowser.qt.gui import QFont
# pylint: disable=no-name-in-module
from qutebrowser.qt.webkit import QWebSettings
from qutebrowser.qt.webkitwidgets import QWebPage
# pylint: enable=no-name-in-module

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
            Attr(QWebSettings.WebAttribute.AutoLoadImages),
        'content.javascript.enabled':
            Attr(QWebSettings.WebAttribute.JavascriptEnabled),
        'content.javascript.can_open_tabs_automatically':
            Attr(QWebSettings.WebAttribute.JavascriptCanOpenWindows),
        'content.javascript.can_close_tabs':
            Attr(QWebSettings.WebAttribute.JavascriptCanCloseWindows),
        'content.javascript.clipboard':
            Attr(QWebSettings.WebAttribute.JavascriptCanAccessClipboard,
                 converter=lambda val: val != "none"),
        'content.plugins':
            Attr(QWebSettings.WebAttribute.PluginsEnabled),
        'content.webgl':
            Attr(QWebSettings.WebAttribute.WebGLEnabled),
        'content.hyperlink_auditing':
            Attr(QWebSettings.WebAttribute.HyperlinkAuditingEnabled),
        'content.local_content_can_access_remote_urls':
            Attr(QWebSettings.WebAttribute.LocalContentCanAccessRemoteUrls),
        'content.local_content_can_access_file_urls':
            Attr(QWebSettings.WebAttribute.LocalContentCanAccessFileUrls),
        'content.dns_prefetch':
            Attr(QWebSettings.WebAttribute.DnsPrefetchEnabled),
        'content.frame_flattening':
            Attr(QWebSettings.WebAttribute.FrameFlatteningEnabled),
        'content.cache.appcache':
            Attr(QWebSettings.WebAttribute.OfflineWebApplicationCacheEnabled),
        'content.local_storage':
            Attr(QWebSettings.WebAttribute.LocalStorageEnabled,
                 QWebSettings.WebAttribute.OfflineStorageDatabaseEnabled),
        'content.print_element_backgrounds':
            Attr(QWebSettings.WebAttribute.PrintElementBackgrounds),
        'content.xss_auditing':
            Attr(QWebSettings.WebAttribute.XSSAuditingEnabled),
        'content.site_specific_quirks.enabled':
            Attr(QWebSettings.WebAttribute.SiteSpecificQuirksEnabled),

        'input.spatial_navigation':
            Attr(QWebSettings.WebAttribute.SpatialNavigationEnabled),
        'input.links_included_in_focus_chain':
            Attr(QWebSettings.WebAttribute.LinksIncludedInFocusChain),

        'zoom.text_only':
            Attr(QWebSettings.WebAttribute.ZoomTextOnly),
        'scrolling.smooth':
            Attr(QWebSettings.WebAttribute.ScrollAnimatorEnabled),
    }

    _FONT_SIZES = {
        'fonts.web.size.minimum':
            QWebSettings.FontSize.MinimumFontSize,
        'fonts.web.size.minimum_logical':
            QWebSettings.FontSize.MinimumLogicalFontSize,
        'fonts.web.size.default':
            QWebSettings.FontSize.DefaultFontSize,
        'fonts.web.size.default_fixed':
            QWebSettings.FontSize.DefaultFixedFontSize,
    }

    _FONT_FAMILIES = {
        'fonts.web.family.standard': QWebSettings.FontFamily.StandardFont,
        'fonts.web.family.fixed': QWebSettings.FontFamily.FixedFont,
        'fonts.web.family.serif': QWebSettings.FontFamily.SerifFont,
        'fonts.web.family.sans_serif': QWebSettings.FontFamily.SansSerifFont,
        'fonts.web.family.cursive': QWebSettings.FontFamily.CursiveFont,
        'fonts.web.family.fantasy': QWebSettings.FontFamily.FantasyFont,
    }

    # Mapping from QWebSettings::QWebSettings() in
    # qtwebkit/Source/WebKit/qt/Api/qwebsettings.cpp
    _FONT_TO_QFONT = {
        QWebSettings.FontFamily.StandardFont: QFont.StyleHint.Serif,
        QWebSettings.FontFamily.FixedFont: QFont.StyleHint.Monospace,
        QWebSettings.FontFamily.SerifFont: QFont.StyleHint.Serif,
        QWebSettings.FontFamily.SansSerifFont: QFont.StyleHint.SansSerif,
        QWebSettings.FontFamily.CursiveFont: QFont.StyleHint.Cursive,
        QWebSettings.FontFamily.FantasyFont: QFont.StyleHint.Fantasy,
    }


def _set_user_stylesheet(settings):
    """Set the generated user-stylesheet."""
    stylesheet = shared.get_user_stylesheet().encode('utf-8')
    url = urlutils.data_url('text/css;charset=utf-8', stylesheet)
    settings.setUserStyleSheetUrl(url)


def _set_cookie_accept_policy(settings):
    """Update the content.cookies.accept setting."""
    mapping = {
        'all': QWebSettings.ThirdPartyCookiePolicy.AlwaysAllowThirdPartyCookies,
        'no-3rdparty': QWebSettings.ThirdPartyCookiePolicy.AlwaysBlockThirdPartyCookies,
        'never': QWebSettings.ThirdPartyCookiePolicy.AlwaysBlockThirdPartyCookies,
        'no-unknown-3rdparty': QWebSettings.ThirdPartyCookiePolicy.AllowThirdPartyWithExistingCookies,
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


def init():
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
