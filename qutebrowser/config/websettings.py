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
"""

import os.path

from PyQt5.QtWebKit import QWebSettings

from qutebrowser.config import config
from qutebrowser.utils import standarddir, objreg, log, utils, debug

UNSET = object()


class Base:

    """Base class for QWebSetting wrappers.

    Attributes:
        _default: The default value of this setting.
    """

    def __init__(self):
        self._default = UNSET

    def _get_qws(self, qws):
        """Get the QWebSettings object to use.

        Args:
            qws: The QWebSettings instance to use, or None to use the global
                 instance.
        """
        if qws is None:
            return QWebSettings.globalSettings()
        else:
            return qws

    def save_default(self, qws=None):
        """Save the default value based on the currently set one.

        This does nothing if no getter is configured for this setting.

        Args:
            qws: The QWebSettings instance to use, or None to use the global
                 instance.

        Return:
            The saved default value.
        """
        try:
            self._default = self.get(qws)
            return self._default
        except AttributeError:
            return None

    def restore_default(self, qws=None):
        """Restore the default value from the saved one.

        This does nothing if the default has never been set.

        Args:
            qws: The QWebSettings instance to use, or None to use the global
                 instance.
        """
        if self._default is not UNSET:
            log.config.vdebug("Restoring default {!r}.".format(self._default))
            self._set(self._default, qws=qws)

    def get(self, qws=None):
        """Get the value of this setting.

        Must be overridden by subclasses.

        Args:
            qws: The QWebSettings instance to use, or None to use the global
                 instance.
        """
        raise NotImplementedError

    def set(self, value, qws=None):
        """Set the value of this setting.

        Args:
            value: The value to set.
            qws: The QWebSettings instance to use, or None to use the global
                 instance.
        """
        if value is None:
            self.restore_default(qws)
        else:
            self._set(value, qws=qws)

    def _set(self, value, qws):
        """Inner function to set the value of this setting.

        Must be overridden by subclasses.

        Args:
            value: The value to set.
            qws: The QWebSettings instance to use, or None to use the global
                 instance.
        """
        raise NotImplementedError


class Attribute(Base):

    """A setting set via QWebSettings::setAttribute.

    Attributes:
        self._attribute: A QWebSettings::WebAttribute instance.
    """

    def __init__(self, attribute):
        super().__init__()
        self._attribute = attribute

    def __repr__(self):
        return utils.get_repr(
            self, attribute=debug.qenum_key(QWebSettings, self._attribute),
            constructor=True)

    def get(self, qws=None):
        return self._get_qws(qws).attribute(self._attribute)

    def _set(self, value, qws=None):
        self._get_qws(qws).setAttribute(self._attribute, value)


class Setter(Base):

    """A setting set via QWebSettings getter/setter methods.

    This will pass the QWebSettings instance ("self") as first argument to the
    methods, so self._getter/self._setter are the *unbound* methods.

    Attributes:
        _getter: The unbound QWebSettings method to get this value, or None.
        _setter: The unbound QWebSettings method to set this value.
        _args: An iterable of the arguments to pass to the setter/getter
               (before the value, for the setter).
        _unpack: Whether to unpack args (True) or pass them directly (False).
    """

    def __init__(self, getter, setter, args=(), unpack=False):
        super().__init__()
        self._getter = getter
        self._setter = setter
        self._args = args
        self._unpack = unpack

    def __repr__(self):
        return utils.get_repr(self, getter=self._getter, setter=self._setter,
                              args=self._args, unpack=self._unpack,
                              constructor=True)

    def get(self, qws=None):
        if self._getter is None:
            raise AttributeError("No getter set!")
        return self._getter(self._get_qws(qws), *self._args)

    def _set(self, value, qws=None):
        args = [self._get_qws(qws)]
        args.extend(self._args)
        if self._unpack:
            args.extend(value)
        else:
            args.append(value)
        self._setter(*args)


class NullStringSetter(Setter):

    """A setter for settings requiring a null QString as default.

    This overrides save_default so None is saved for an empty string. This is
    needed for the CSS media type, because it returns an empty Python string
    when getting the value, but setting it to the default requires passing None
    (a null QString) instead of an empty string.
    """

    def save_default(self, qws=None):
        try:
            val = self.get(qws)
        except AttributeError:
            return None
        if val == '':
            self._set(None, qws=qws)
        else:
            self._set(val, qws=qws)
        return val


class GlobalSetter(Setter):

    """A setting set via static QWebSettings getter/setter methods.

    self._getter/self._setter are the *bound* methods.
    """

    def get(self, qws=None):
        if qws is not None:
            raise ValueError("qws may not be set with GlobalSetters!")
        if self._getter is None:
            raise AttributeError("No getter set!")
        return self._getter(*self._args)

    def _set(self, value, qws=None):
        if qws is not None:
            raise ValueError("qws may not be set with GlobalSetters!")
        args = list(self._args)
        if self._unpack:
            args.extend(value)
        else:
            args.append(value)
        self._setter(*args)


class CookiePolicy(Base):

    """The ThirdPartyCookiePolicy setting is different from other settings."""

    MAPPING = {
        'all': QWebSettings.AlwaysAllowThirdPartyCookies,
        'no-3rdparty': QWebSettings.AlwaysBlockThirdPartyCookies,
        'never': QWebSettings.AlwaysBlockThirdPartyCookies,
        'no-unknown-3rdparty': QWebSettings.AllowThirdPartyWithExistingCookies,
    }

    def get(self, qws=None):
        return config.get('content', 'cookies-accept')

    def _set(self, value, qws=None):
        QWebSettings.globalSettings().setThirdPartyCookiePolicy(
            self.MAPPING[value])


MAPPINGS = {
    'content': {
        'allow-images':
            Attribute(QWebSettings.AutoLoadImages),
        'allow-javascript':
            Attribute(QWebSettings.JavascriptEnabled),
        'javascript-can-open-windows':
            Attribute(QWebSettings.JavascriptCanOpenWindows),
        'javascript-can-close-windows':
            Attribute(QWebSettings.JavascriptCanCloseWindows),
        'javascript-can-access-clipboard':
            Attribute(QWebSettings.JavascriptCanAccessClipboard),
        #'allow-java':
        #   Attribute(QWebSettings.JavaEnabled),
        'allow-plugins':
            Attribute(QWebSettings.PluginsEnabled),
        'webgl':
            Attribute(QWebSettings.WebGLEnabled),
        'css-regions':
            Attribute(QWebSettings.CSSRegionsEnabled),
        'hyperlink-auditing':
            Attribute(QWebSettings.HyperlinkAuditingEnabled),
        'local-content-can-access-remote-urls':
            Attribute(QWebSettings.LocalContentCanAccessRemoteUrls),
        'local-content-can-access-file-urls':
            Attribute(QWebSettings.LocalContentCanAccessFileUrls),
        'cookies-accept':
            CookiePolicy(),
    },
    'network': {
        'dns-prefetch':
            Attribute(QWebSettings.DnsPrefetchEnabled),
    },
    'input': {
        'spatial-navigation':
            Attribute(QWebSettings.SpatialNavigationEnabled),
        'links-included-in-focus-chain':
            Attribute(QWebSettings.LinksIncludedInFocusChain),
    },
    'fonts': {
        'web-family-standard':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.StandardFont]),
        'web-family-fixed':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.FixedFont]),
        'web-family-serif':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.SerifFont]),
        'web-family-sans-serif':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.SansSerifFont]),
        'web-family-cursive':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.CursiveFont]),
        'web-family-fantasy':
            Setter(getter=QWebSettings.fontFamily,
                   setter=QWebSettings.setFontFamily,
                   args=[QWebSettings.FantasyFont]),
        'web-size-minimum':
            Setter(getter=QWebSettings.fontSize,
                   setter=QWebSettings.setFontSize,
                   args=[QWebSettings.MinimumFontSize]),
        'web-size-minimum-logical':
            Setter(getter=QWebSettings.fontSize,
                   setter=QWebSettings.setFontSize,
                   args=[QWebSettings.MinimumLogicalFontSize]),
        'web-size-default':
            Setter(getter=QWebSettings.fontSize,
                   setter=QWebSettings.setFontSize,
                   args=[QWebSettings.DefaultFontSize]),
        'web-size-default-fixed':
            Setter(getter=QWebSettings.fontSize,
                   setter=QWebSettings.setFontSize,
                   args=[QWebSettings.DefaultFixedFontSize]),
    },
    'ui': {
        'zoom-text-only':
            Attribute(QWebSettings.ZoomTextOnly),
        'frame-flattening':
            Attribute(QWebSettings.FrameFlatteningEnabled),
        'user-stylesheet':
            Setter(getter=QWebSettings.userStyleSheetUrl,
                   setter=QWebSettings.setUserStyleSheetUrl),
        'css-media-type':
            NullStringSetter(getter=QWebSettings.cssMediaType,
                             setter=QWebSettings.setCSSMediaType),
        'smooth-scrolling':
            Attribute(QWebSettings.ScrollAnimatorEnabled),
        #'accelerated-compositing':
        #   Attribute(QWebSettings.AcceleratedCompositingEnabled),
        #'tiled-backing-store':
        #   Attribute(QWebSettings.TiledBackingStoreEnabled),
    },
    'storage': {
        'offline-storage-database':
            Attribute(QWebSettings.OfflineStorageDatabaseEnabled),
        'offline-web-application-storage':
            Attribute(QWebSettings.OfflineWebApplicationCacheEnabled),
        'local-storage':
            Attribute(QWebSettings.LocalStorageEnabled),
        'maximum-pages-in-cache':
            GlobalSetter(getter=QWebSettings.maximumPagesInCache,
                         setter=QWebSettings.setMaximumPagesInCache),
        'object-cache-capacities':
            GlobalSetter(getter=None,
                         setter=QWebSettings.setObjectCacheCapacities,
                         unpack=True),
        'offline-storage-default-quota':
            GlobalSetter(getter=QWebSettings.offlineStorageDefaultQuota,
                         setter=QWebSettings.setOfflineStorageDefaultQuota),
        'offline-web-application-cache-quota':
            GlobalSetter(
                getter=QWebSettings.offlineWebApplicationCacheQuota,
                setter=QWebSettings.setOfflineWebApplicationCacheQuota),
    },
    'general': {
        'private-browsing':
            Attribute(QWebSettings.PrivateBrowsingEnabled),
        'developer-extras':
            Attribute(QWebSettings.DeveloperExtrasEnabled),
        'print-element-backgrounds':
            Attribute(QWebSettings.PrintElementBackgrounds),
        'xss-auditing':
            Attribute(QWebSettings.XSSAuditingEnabled),
        'site-specific-quirks':
            Attribute(QWebSettings.SiteSpecificQuirksEnabled),
        'default-encoding':
            Setter(getter=QWebSettings.defaultTextEncoding,
                   setter=QWebSettings.setDefaultTextEncoding),
    }
}


def init():
    """Initialize the global QWebSettings."""
    cache_path = standarddir.cache()
    data_path = standarddir.data()
    if config.get('general', 'private-browsing') or cache_path is None:
        QWebSettings.setIconDatabasePath('')
    else:
        QWebSettings.setIconDatabasePath(cache_path)
    if cache_path is not None:
        QWebSettings.setOfflineWebApplicationCachePath(
            os.path.join(cache_path, 'application-cache'))
    if data_path is not None:
        QWebSettings.globalSettings().setLocalStoragePath(
            os.path.join(data_path, 'local-storage'))
        QWebSettings.setOfflineStoragePath(
            os.path.join(data_path, 'offline-storage'))

    for sectname, section in MAPPINGS.items():
        for optname, mapping in section.items():
            default = mapping.save_default()
            log.config.vdebug("Saved default for {} -> {}: {!r}".format(
                sectname, optname, default))
            value = config.get(sectname, optname)
            log.config.vdebug("Setting {} -> {} to {!r}".format(
                sectname, optname, value))
            mapping.set(value)
    objreg.get('config').changed.connect(update_settings)


def update_settings(section, option):
    """Update global settings when qwebsettings changed."""
    cache_path = standarddir.cache()
    if (section, option) == ('general', 'private-browsing'):
        if config.get('general', 'private-browsing') or cache_path is None:
            QWebSettings.setIconDatabasePath('')
        else:
            QWebSettings.setIconDatabasePath(cache_path)
    else:
        try:
            mapping = MAPPINGS[section][option]
        except KeyError:
            return
        value = config.get(section, option)
        mapping.set(value)
