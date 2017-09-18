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
from qutebrowser.utils import standarddir, urlutils
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


def _update_settings(option):
    """Update global settings when qwebsettings changed."""
    if option in ['scrollbar.hide', 'content.user_stylesheets']:
        _set_user_stylesheet()
    websettings.update_mappings(MAPPINGS, option)


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

    websettings.init_mappings(MAPPINGS)
    _set_user_stylesheet()
    config.instance.changed.connect(_update_settings)


def shutdown():
    """Disable storage so removing tmpdir will work."""
    QWebSettings.setIconDatabasePath('')
    QWebSettings.setOfflineWebApplicationCachePath('')
    QWebSettings.globalSettings().setLocalStoragePath('')


MAPPINGS = {
    'content.images':
        Attribute(QWebSettings.AutoLoadImages),
    'content.javascript.enabled':
        Attribute(QWebSettings.JavascriptEnabled),
    'content.javascript.can_open_tabs_automatically':
        Attribute(QWebSettings.JavascriptCanOpenWindows),
    'content.javascript.can_close_tabs':
        Attribute(QWebSettings.JavascriptCanCloseWindows),
    'content.javascript.can_access_clipboard':
        Attribute(QWebSettings.JavascriptCanAccessClipboard),
    'content.plugins':
        Attribute(QWebSettings.PluginsEnabled),
    'content.webgl':
        Attribute(QWebSettings.WebGLEnabled),
    'content.hyperlink_auditing':
        Attribute(QWebSettings.HyperlinkAuditingEnabled),
    'content.local_content_can_access_remote_urls':
        Attribute(QWebSettings.LocalContentCanAccessRemoteUrls),
    'content.local_content_can_access_file_urls':
        Attribute(QWebSettings.LocalContentCanAccessFileUrls),
    'content.cookies.accept':
        CookiePolicy(),
    'content.dns_prefetch':
        Attribute(QWebSettings.DnsPrefetchEnabled),
    'content.frame_flattening':
        Attribute(QWebSettings.FrameFlatteningEnabled),
    'content.cache.appcache':
        Attribute(QWebSettings.OfflineWebApplicationCacheEnabled),
    'content.local_storage':
        Attribute(QWebSettings.LocalStorageEnabled,
                  QWebSettings.OfflineStorageDatabaseEnabled),
    'content.cache.maximum_pages':
        StaticSetter(QWebSettings.setMaximumPagesInCache),
    'content.developer_extras':
        Attribute(QWebSettings.DeveloperExtrasEnabled),
    'content.print_element_backgrounds':
        Attribute(QWebSettings.PrintElementBackgrounds),
    'content.xss_auditing':
        Attribute(QWebSettings.XSSAuditingEnabled),
    'content.default_encoding':
        Setter(QWebSettings.setDefaultTextEncoding),
    # content.user_stylesheets is handled separately

    'input.spatial_navigation':
        Attribute(QWebSettings.SpatialNavigationEnabled),
    'input.links_included_in_focus_chain':
        Attribute(QWebSettings.LinksIncludedInFocusChain),

    'fonts.web.family.standard':
        FontFamilySetter(QWebSettings.StandardFont),
    'fonts.web.family.fixed':
        FontFamilySetter(QWebSettings.FixedFont),
    'fonts.web.family.serif':
        FontFamilySetter(QWebSettings.SerifFont),
    'fonts.web.family.sans_serif':
        FontFamilySetter(QWebSettings.SansSerifFont),
    'fonts.web.family.cursive':
        FontFamilySetter(QWebSettings.CursiveFont),
    'fonts.web.family.fantasy':
        FontFamilySetter(QWebSettings.FantasyFont),
    'fonts.web.size.minimum':
        Setter(QWebSettings.setFontSize, args=[QWebSettings.MinimumFontSize]),
    'fonts.web.size.minimum_logical':
        Setter(QWebSettings.setFontSize,
               args=[QWebSettings.MinimumLogicalFontSize]),
    'fonts.web.size.default':
        Setter(QWebSettings.setFontSize, args=[QWebSettings.DefaultFontSize]),
    'fonts.web.size.default_fixed':
        Setter(QWebSettings.setFontSize,
               args=[QWebSettings.DefaultFixedFontSize]),

    'zoom.text_only':
        Attribute(QWebSettings.ZoomTextOnly),
    'scrolling.smooth':
        Attribute(QWebSettings.ScrollAnimatorEnabled),
}
