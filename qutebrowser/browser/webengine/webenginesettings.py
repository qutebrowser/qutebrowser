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

"""Bridge from QWebEngineSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebEngineSetting enum
                constants.
"""

import os

# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.config import websettings, config
from qutebrowser.utils import objreg, utils


class Attribute(websettings.Attribute):

    GLOBAL_SETTINGS = QWebEngineSettings.globalSettings
    ENUM_BASE = QWebEngineSettings


class Setter(websettings.Setter):

    GLOBAL_SETTINGS = QWebEngineSettings.globalSettings


class NullStringSetter(websettings.NullStringSetter):

    GLOBAL_SETTINGS = QWebEngineSettings.globalSettings


class StaticSetter(websettings.StaticSetter):

    GLOBAL_SETTINGS = QWebEngineSettings.globalSettings


def update_settings(section, option):
    """Update global settings when qwebsettings changed."""
    websettings.update_mappings(MAPPINGS, section, option)


def init():
    """Initialize the global QWebSettings."""
    # FIXME:qtwebengine set paths in profile

    if config.get('general', 'developer-extras'):
        # FIXME:qtwebengine Make sure we call globalSettings *after* this...
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = str(utils.random_port())

    websettings.init_mappings(MAPPINGS)
    objreg.get('config').changed.connect(update_settings)


# Missing QtWebEngine attributes:
# - ErrorPageEnabled (should not be exposed, but set)
# - FullScreenSupportEnabled
# - ScreenCaptureEnabled
# - Accelerated2dCanvasEnabled
# - AutoLoadIconsForPage
# - TouchIconsEnabled
#
# Missing QtWebEngine fonts:
# - FantasyFont
# - PictographFont
#
# TODO settings on profile:
# - cachePath
# - httpAcceptLanguage
# - httpCacheMaximumSize
# - httpUserAgent
# - persistentCookiesPolicy
# - offTheRecord
# - persistentStoragePath
#
# TODO settings elsewhere:
# - proxy
# - custom headers
# - ssl-strict

MAPPINGS = {
    'content': {
        'allow-images':
            Attribute(QWebEngineSettings.AutoLoadImages),
        'allow-javascript':
            Attribute(QWebEngineSettings.JavascriptEnabled),
        'javascript-can-open-windows':
            Attribute(QWebEngineSettings.JavascriptCanOpenWindows),
        'javascript-can-access-clipboard':
            Attribute(QWebEngineSettings.JavascriptCanAccessClipboard),
        'allow-plugins':
            Attribute(QWebEngineSettings.PluginsEnabled),
        'hyperlink-auditing':
            Attribute(QWebEngineSettings.HyperlinkAuditingEnabled),
        'local-content-can-access-remote-urls':
            Attribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls),
        'local-content-can-access-file-urls':
            Attribute(QWebEngineSettings.LocalContentCanAccessFileUrls),
    },
    'input': {
        'spatial-navigation':
            Attribute(QWebEngineSettings.SpatialNavigationEnabled),
        'links-included-in-focus-chain':
            Attribute(QWebEngineSettings.LinksIncludedInFocusChain),
    },
    'fonts': {
        'web-family-standard':
            Setter(getter=QWebEngineSettings.fontFamily,
                   setter=QWebEngineSettings.setFontFamily,
                   args=[QWebEngineSettings.StandardFont]),
        'web-family-fixed':
            Setter(getter=QWebEngineSettings.fontFamily,
                   setter=QWebEngineSettings.setFontFamily,
                   args=[QWebEngineSettings.FixedFont]),
        'web-family-serif':
            Setter(getter=QWebEngineSettings.fontFamily,
                   setter=QWebEngineSettings.setFontFamily,
                   args=[QWebEngineSettings.SerifFont]),
        'web-family-sans-serif':
            Setter(getter=QWebEngineSettings.fontFamily,
                   setter=QWebEngineSettings.setFontFamily,
                   args=[QWebEngineSettings.SansSerifFont]),
        'web-family-cursive':
            Setter(getter=QWebEngineSettings.fontFamily,
                   setter=QWebEngineSettings.setFontFamily,
                   args=[QWebEngineSettings.CursiveFont]),
        'web-family-fantasy':
            Setter(getter=QWebEngineSettings.fontFamily,
                   setter=QWebEngineSettings.setFontFamily,
                   args=[QWebEngineSettings.FantasyFont]),
        'web-size-minimum':
            Setter(getter=QWebEngineSettings.fontSize,
                   setter=QWebEngineSettings.setFontSize,
                   args=[QWebEngineSettings.MinimumFontSize]),
        'web-size-minimum-logical':
            Setter(getter=QWebEngineSettings.fontSize,
                   setter=QWebEngineSettings.setFontSize,
                   args=[QWebEngineSettings.MinimumLogicalFontSize]),
        'web-size-default':
            Setter(getter=QWebEngineSettings.fontSize,
                   setter=QWebEngineSettings.setFontSize,
                   args=[QWebEngineSettings.DefaultFontSize]),
        'web-size-default-fixed':
            Setter(getter=QWebEngineSettings.fontSize,
                   setter=QWebEngineSettings.setFontSize,
                   args=[QWebEngineSettings.DefaultFixedFontSize]),
    },
    'ui': {
        'smooth-scrolling':
            Attribute(QWebEngineSettings.ScrollAnimatorEnabled),
    },
    'storage': {
        'local-storage':
            Attribute(QWebEngineSettings.LocalStorageEnabled),
    },
    'general': {
        'xss-auditing':
            Attribute(QWebEngineSettings.XSSAuditingEnabled),
        'default-encoding':
            Setter(getter=QWebEngineSettings.defaultTextEncoding,
                   setter=QWebEngineSettings.setDefaultTextEncoding),
    }
}

try:
    MAPPINGS['content']['webgl'] = Attribute(QWebEngineSettings.WebGLEnabled)
except AttributeError:
    # Added in Qt 5.7
    pass
