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
from PyQt5.QtWebEngineWidgets import (QWebEngineSettings, QWebEngineProfile,
                                      QWebEngineScript)
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.browser import shared
from qutebrowser.config import websettings
from qutebrowser.utils import objreg, utils, standarddir, javascript


class Attribute(websettings.Attribute):

    """A setting set via QWebEngineSettings::setAttribute."""

    GLOBAL_SETTINGS = QWebEngineSettings.globalSettings
    ENUM_BASE = QWebEngineSettings


class Setter(websettings.Setter):

    """A setting set via QWebEngineSettings getter/setter methods."""

    GLOBAL_SETTINGS = QWebEngineSettings.globalSettings


class NullStringSetter(websettings.NullStringSetter):

    """A setter for settings requiring a null QString as default."""

    GLOBAL_SETTINGS = QWebEngineSettings.globalSettings


class StaticSetter(websettings.StaticSetter):

    """A setting set via static QWebEngineSettings getter/setter methods."""

    GLOBAL_SETTINGS = QWebEngineSettings.globalSettings


def _init_stylesheet(profile):
    """Initialize custom stylesheets.

    Mostly inspired by QupZilla:
    https://github.com/QupZilla/qupzilla/blob/v2.0/src/lib/app/mainapplication.cpp#L1063-L1101
    https://github.com/QupZilla/qupzilla/blob/v2.0/src/lib/tools/scripts.cpp#L119-L132

    FIXME:qtwebengine Use QWebEngineStyleSheet once that's available
    https://codereview.qt-project.org/#/c/148671/
    """
    old_script = profile.scripts().findScript('_qute_stylesheet')
    if not old_script.isNull():
        profile.scripts().remove(old_script)

    css = shared.get_user_stylesheet()
    source = """
        (function() {{
            var css = document.createElement('style');
            css.setAttribute('type', 'text/css');
            css.appendChild(document.createTextNode('{}'));
            document.getElementsByTagName('head')[0].appendChild(css);
        }})()
    """.format(javascript.string_escape(css))

    script = QWebEngineScript()
    script.setName('_qute_stylesheet')
    script.setInjectionPoint(QWebEngineScript.DocumentReady)
    script.setWorldId(QWebEngineScript.ApplicationWorld)
    script.setRunsOnSubFrames(True)
    script.setSourceCode(source)
    profile.scripts().insert(script)


def update_settings(section, option):
    """Update global settings when qwebsettings changed."""
    websettings.update_mappings(MAPPINGS, section, option)
    profile = QWebEngineProfile.defaultProfile()
    if section == 'ui' and option in ['hide-scrollbar', 'user-stylesheet']:
        _init_stylesheet(profile)


def init(args):
    """Initialize the global QWebSettings."""
    if args.enable_webengine_inspector:
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = str(utils.random_port())

    profile = QWebEngineProfile.defaultProfile()
    profile.setCachePath(os.path.join(standarddir.cache(), 'webengine'))
    profile.setPersistentStoragePath(
        os.path.join(standarddir.data(), 'webengine'))
    _init_stylesheet(profile)

    websettings.init_mappings(MAPPINGS)
    objreg.get('config').changed.connect(update_settings)


def shutdown():
    # FIXME:qtwebengine do we need to do something for a clean shutdown here?
    pass


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
# - httpCacheMaximumSize
# - persistentCookiesPolicy
# - offTheRecord
#
# TODO settings elsewhere:
# - proxy

MAPPINGS = {
    'content': {
        'allow-images':
            Attribute(QWebEngineSettings.AutoLoadImages),
        'allow-javascript':
            Attribute(QWebEngineSettings.JavascriptEnabled),
        'javascript-can-open-windows-automatically':
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
