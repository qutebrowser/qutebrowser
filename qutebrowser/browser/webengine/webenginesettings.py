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

"""Bridge from QWebEngineSettings to our own settings.

Module attributes:
    ATTRIBUTES: A mapping from internal setting names to QWebEngineSetting enum
                constants.
"""

import os
import operator
import pathlib
import functools
import dataclasses
from typing import cast, Any, List, Optional, Tuple, Union, TYPE_CHECKING

from qutebrowser.qt import machinery
from qutebrowser.qt.gui import QFont
from qutebrowser.qt.widgets import QApplication
from qutebrowser.qt.webenginecore import (
    QWebEngineSettings, QWebEngineProfile, QWebEngineScript,
)

from qutebrowser.browser import history, shared, greasemonkey
from qutebrowser.browser.webengine import (spell, webenginequtescheme, cookies,
                                           webenginedownloads, notification)
from qutebrowser.config import config, websettings
from qutebrowser.config.websettings import AttributeInfo as Attr
from qutebrowser.utils import (standarddir, qtutils, message, log,
                               urlmatch, usertypes, objreg, version,
                               javascript, resources, utils)
if TYPE_CHECKING:
    from qutebrowser.browser.webengine import interceptor

# The default QWebEngineProfile
default_profile = cast(QWebEngineProfile, None)
# The QWebEngineProfile used for private (off-the-record) windows
private_profile: Optional[QWebEngineProfile] = None
# The global WebEngineSettings object
_global_settings = cast('WebEngineSettings', None)

parsed_user_agent = None

_qute_scheme_handler = cast(webenginequtescheme.QuteSchemeHandler, None)
_req_interceptor = cast('interceptor.RequestInterceptor', None)
_download_manager = cast(webenginedownloads.DownloadManager, None)


class _SettingsWrapper:

    """Expose a QWebEngineSettings interface which acts on all profiles.

    For read operations, the default profile value is always used.
    """

    def _settings(self):
        yield default_profile.settings()
        if private_profile:
            yield private_profile.settings()

    def setAttribute(self, attribute, on):
        for settings in self._settings():
            settings.setAttribute(attribute, on)

    def setFontFamily(self, which, family):
        for settings in self._settings():
            settings.setFontFamily(which, family)

    def setFontSize(self, fonttype, size):
        for settings in self._settings():
            settings.setFontSize(fonttype, size)

    def setDefaultTextEncoding(self, encoding):
        for settings in self._settings():
            settings.setDefaultTextEncoding(encoding)

    def setUnknownUrlSchemePolicy(self, policy):
        for settings in self._settings():
            settings.setUnknownUrlSchemePolicy(policy)

    def testAttribute(self, attribute):
        return default_profile.settings().testAttribute(attribute)

    def fontSize(self, fonttype):
        return default_profile.settings().fontSize(fonttype)

    def fontFamily(self, which):
        return default_profile.settings().fontFamily(which)

    def defaultTextEncoding(self):
        return default_profile.settings().defaultTextEncoding()

    def unknownUrlSchemePolicy(self):
        return default_profile.settings().unknownUrlSchemePolicy()


class WebEngineSettings(websettings.AbstractSettings):

    """A wrapper for the config for QWebEngineSettings."""

    _ATTRIBUTES = {
        'content.xss_auditing':
            Attr(QWebEngineSettings.WebAttribute.XSSAuditingEnabled),
        'content.images':
            Attr(QWebEngineSettings.WebAttribute.AutoLoadImages),
        'content.javascript.enabled':
            Attr(QWebEngineSettings.WebAttribute.JavascriptEnabled),
        'content.javascript.can_open_tabs_automatically':
            Attr(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows),
        'content.plugins':
            Attr(QWebEngineSettings.WebAttribute.PluginsEnabled),
        'content.hyperlink_auditing':
            Attr(QWebEngineSettings.WebAttribute.HyperlinkAuditingEnabled),
        'content.local_content_can_access_remote_urls':
            Attr(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls),
        'content.local_content_can_access_file_urls':
            Attr(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls),
        'content.webgl':
            Attr(QWebEngineSettings.WebAttribute.WebGLEnabled),
        'content.local_storage':
            Attr(QWebEngineSettings.WebAttribute.LocalStorageEnabled),
        'content.desktop_capture':
            Attr(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled,
                 converter=lambda val: True if val == 'ask' else val),
        # 'ask' is handled via the permission system

        'input.spatial_navigation':
            Attr(QWebEngineSettings.WebAttribute.SpatialNavigationEnabled),
        'input.links_included_in_focus_chain':
            Attr(QWebEngineSettings.WebAttribute.LinksIncludedInFocusChain),

        'scrolling.smooth':
            Attr(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled),

        'content.print_element_backgrounds':
            Attr(QWebEngineSettings.WebAttribute.PrintElementBackgrounds),

        'content.autoplay':
            Attr(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture,
                 converter=operator.not_),

        'content.dns_prefetch':
            Attr(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled),

        'tabs.favicons.show':
            Attr(QWebEngineSettings.WebAttribute.AutoLoadIconsForPage,
                 converter=lambda val: val != 'never'),
    }

    _FONT_SIZES = {
        'fonts.web.size.minimum':
            QWebEngineSettings.FontSize.MinimumFontSize,
        'fonts.web.size.minimum_logical':
            QWebEngineSettings.FontSize.MinimumLogicalFontSize,
        'fonts.web.size.default':
            QWebEngineSettings.FontSize.DefaultFontSize,
        'fonts.web.size.default_fixed':
            QWebEngineSettings.FontSize.DefaultFixedFontSize,
    }

    _FONT_FAMILIES = {
        'fonts.web.family.standard': QWebEngineSettings.FontFamily.StandardFont,
        'fonts.web.family.fixed': QWebEngineSettings.FontFamily.FixedFont,
        'fonts.web.family.serif': QWebEngineSettings.FontFamily.SerifFont,
        'fonts.web.family.sans_serif': QWebEngineSettings.FontFamily.SansSerifFont,
        'fonts.web.family.cursive': QWebEngineSettings.FontFamily.CursiveFont,
        'fonts.web.family.fantasy': QWebEngineSettings.FontFamily.FantasyFont,
    }

    _UNKNOWN_URL_SCHEME_POLICY = {
        'disallow':
            QWebEngineSettings.UnknownUrlSchemePolicy.DisallowUnknownUrlSchemes,
        'allow-from-user-interaction':
            QWebEngineSettings.UnknownUrlSchemePolicy.AllowUnknownUrlSchemesFromUserInteraction,
        'allow-all':
            QWebEngineSettings.UnknownUrlSchemePolicy.AllowAllUnknownUrlSchemes,
    }

    # Mapping from WebEngineSettings::initDefaults in
    # qtwebengine/src/core/web_engine_settings.cpp
    _FONT_TO_QFONT = {
        QWebEngineSettings.FontFamily.StandardFont: QFont.StyleHint.Serif,
        QWebEngineSettings.FontFamily.FixedFont: QFont.StyleHint.Monospace,
        QWebEngineSettings.FontFamily.SerifFont: QFont.StyleHint.Serif,
        QWebEngineSettings.FontFamily.SansSerifFont: QFont.StyleHint.SansSerif,
        QWebEngineSettings.FontFamily.CursiveFont: QFont.StyleHint.Cursive,
        QWebEngineSettings.FontFamily.FantasyFont: QFont.StyleHint.Fantasy,
    }

    _JS_CLIPBOARD_SETTINGS = {
        'none': {
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard: False,
            QWebEngineSettings.WebAttribute.JavascriptCanPaste: False,
        },
        'access': {
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard: True,
            QWebEngineSettings.WebAttribute.JavascriptCanPaste: False,
        },
        'access-paste': {
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard: True,
            QWebEngineSettings.WebAttribute.JavascriptCanPaste: True,
        },
    }

    def set_unknown_url_scheme_policy(
            self, policy: Union[str, usertypes.Unset]) -> None:
        """Set the UnknownUrlSchemePolicy to use."""
        if isinstance(policy, usertypes.Unset):
            self._settings.resetUnknownUrlSchemePolicy()
        else:
            new_value = self._UNKNOWN_URL_SCHEME_POLICY[policy]
            self._settings.setUnknownUrlSchemePolicy(new_value)

    def _set_js_clipboard(self, value: Union[str, usertypes.Unset]) -> None:
        attr_access = QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard
        attr_paste = QWebEngineSettings.WebAttribute.JavascriptCanPaste

        if isinstance(value, usertypes.Unset):
            self._settings.resetAttribute(attr_access)
            self._settings.resetAttribute(attr_paste)
        else:
            for attr, attr_val in self._JS_CLIPBOARD_SETTINGS[value].items():
                self._settings.setAttribute(attr, attr_val)

    def _update_setting(self, setting, value):
        if setting == 'content.unknown_url_scheme_policy':
            self.set_unknown_url_scheme_policy(value)
        elif setting == 'content.javascript.clipboard':
            self._set_js_clipboard(value)
        # NOTE: When adding something here, also add it to init_settings()!
        super()._update_setting(setting, value)

    def init_settings(self):
        super().init_settings()
        self.update_setting('content.unknown_url_scheme_policy')
        self.update_setting('content.javascript.clipboard')


class ProfileSetter:

    """Helper to set various settings on a profile."""

    def __init__(self, profile):
        self._profile = profile
        self._name_to_method = {
            'content.cache.size': self.set_http_cache_size,
            'content.cookies.store': self.set_persistent_cookie_policy,
            'spellcheck.languages': self.set_dictionary_language,
            'content.headers.user_agent': self.set_http_headers,
            'content.headers.accept_language': self.set_http_headers,
        }

    def update_setting(self, name):
        """Update a setting based on its name."""
        try:
            meth = self._name_to_method[name]
        except KeyError:
            return
        meth()

    def init_profile(self):
        """Initialize settings on the given profile."""
        self.set_http_headers()
        self.set_http_cache_size()
        self._set_hardcoded_settings()
        self.set_persistent_cookie_policy()
        self.set_dictionary_language()

    def _set_hardcoded_settings(self):
        """Set up settings with a fixed value."""
        settings = self._profile.settings()

        settings.setAttribute(
            QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, False)

    def set_http_headers(self):
        """Set the user agent and accept-language for the given profile.

        We override those per request in the URL interceptor (to allow for
        per-domain values), but this one still gets used for things like
        window.navigator.userAgent/.languages in JS.
        """
        user_agent = websettings.user_agent()
        self._profile.setHttpUserAgent(user_agent)

        accept_language = config.val.content.headers.accept_language
        if accept_language is not None:
            self._profile.setHttpAcceptLanguage(accept_language)

    def set_http_cache_size(self):
        """Initialize the HTTP cache size for the given profile."""
        size = config.val.content.cache.size
        if size is None:
            size = 0
        else:
            size = qtutils.check_overflow(size, 'int', fatal=False)

        # 0: automatically managed by QtWebEngine
        self._profile.setHttpCacheMaximumSize(size)

    def set_persistent_cookie_policy(self):
        """Set the HTTP Cookie size for the given profile."""
        if self._profile.isOffTheRecord():
            return
        if config.val.content.cookies.store:
            value = QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        else:
            value = QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        self._profile.setPersistentCookiesPolicy(value)

    def set_dictionary_language(self):
        """Load the given dictionaries."""
        filenames = []
        for code in config.val.spellcheck.languages or []:
            local_filename = spell.local_filename(code)
            if not local_filename:
                if not self._profile.isOffTheRecord():
                    message.warning("Language {} is not installed - see "
                                    "scripts/dictcli.py in qutebrowser's "
                                    "sources".format(code))
                continue

            filenames.append(os.path.splitext(local_filename)[0])

        log.config.debug("Found dicts: {}".format(filenames))
        self._profile.setSpellCheckLanguages(filenames)
        self._profile.setSpellCheckEnabled(bool(filenames))


def _update_settings(option):
    """Update global settings when qwebsettings changed."""
    _global_settings.update_setting(option)
    default_profile.setter.update_setting(option)  # type: ignore[attr-defined]
    if private_profile:
        private_profile.setter.update_setting(option)  # type: ignore[attr-defined]


def _init_user_agent_str(ua):
    global parsed_user_agent
    parsed_user_agent = websettings.UserAgent.parse(ua)


def init_user_agent():
    _init_user_agent_str(QWebEngineProfile.defaultProfile().httpUserAgent())


# TODO: add to javascript module?
def _script_factory(name, js_code, *,
                    world=QWebEngineScript.ScriptWorldId.ApplicationWorld,
                    injection_point=QWebEngineScript.InjectionPoint.DocumentCreation,
                    subframes=False):
    """Inject the given script to run early on a page load."""
    script = QWebEngineScript()
    script.setInjectionPoint(injection_point)
    script.setSourceCode(js_code)
    script.setWorldId(world)
    script.setRunsOnSubFrames(subframes)
    script.setName(f'_qute_{name}')
    return script


def _remove_js(scripts, name):
    """Remove an early QWebEngineScript."""
    if machinery.IS_QT6:
        for script in scripts.find(f'_qute_{name}'):
            scripts.remove(script)
    else:  # Qt 5
        script = scripts.findScript(f'_qute_{name}')
        if not script.isNull():
            scripts.remove(script)


# TODO: unrelated rambling
# Hmm, change_filter can be told it is being passed a function (unbound
# method) or method (method on an instantiated object). Here I'm telling it
# these are object methods, although they aren't, just because the only
# difference between those modes is that an argument is passed through for the
# object methods. Called "self" in the wrapper it doesn't have to be.
# Probably the change_filter decorator could be changed to support passing
# trough variable arguments and get rid of that split?
# Also it would be nice to have a decorator that did the change filtering and
# handled connecting a signal, and passed the new value into the function.
@config.change_filter('scrolling.bar')
@config.change_filter('content.user_stylesheets')
def _stylesheet_option_changed(profile):
    _inject_stylesheet(profile.scripts())


def _inject_stylesheet(scripts):
    """Initialize custom stylesheets.

    Stylesheet CSS is also overriden in individual tabs when config is updated
    and when find operations are started and ended.

    Partially inspired by QupZilla:
    https://github.com/QupZilla/qupzilla/blob/v2.0/src/lib/app/mainapplication.cpp#L1063-L1101
    """
    _remove_js(scripts, 'stylesheet')
    css = shared.get_user_stylesheet()
    js_code = javascript.wrap_global(
        'stylesheet',
        resources.read_file('javascript/stylesheet.js'),
        javascript.assemble('stylesheet', 'set_css', css),
    )
    scripts.insert(_script_factory('stylesheet', js_code, subframes=True))


def _remove_all_greasemonkey_scripts(profile_scripts):
    for script in profile_scripts.toList():
        if script.name().startswith("GM-"):
            log.greasemonkey.debug('Removing script: {}'
                                   .format(script.name()))
            removed = profile_scripts.remove(script)
            assert removed, script.name()


def _inject_all_greasemonkey_scripts(profile):
    scripts = greasemonkey.gm_manager.all_scripts()
    _inject_greasemonkey_scripts(profile, scripts)


def _inject_greasemonkey_scripts(profile, scripts):
    """Register user JavaScript files with the current tab.

    Args:
        scripts: A list of GreasemonkeyScripts.
    """
    profile_scripts = profile.scripts()
    # Remove and re-add all scripts every time to account for scripts
    # that have been disabled.
    _remove_all_greasemonkey_scripts(profile_scripts)

    seen_names = set()
    for script in scripts:
        while script.full_name() in seen_names:
            script.dedup_suffix += 1
        seen_names.add(script.full_name())

        # TODO: move to use _script_factory to shorten the method?
        new_script = QWebEngineScript()

        try:
            world = int(script.jsworld)
            if not 0 <= world <= qtutils.MAX_WORLD_ID:
                log.greasemonkey.error(
                    f"script {script.name} has invalid value for '@qute-js-world'"
                    f": {script.jsworld}, should be between 0 and "
                    f"{qtutils.MAX_WORLD_ID}")
                continue
        except ValueError:
            try:
                world = qtutils.JS_WORLD_MAP[usertypes.JsWorld[script.jsworld.lower()]]
            except KeyError:
                log.greasemonkey.error(
                    f"script {script.name} has invalid value for '@qute-js-world'"
                    f": {script.jsworld}")
                continue
        new_script.setWorldId(world)

        # Corresponds to "@run-at document-end" which is the default according to
        # https://wiki.greasespot.net/Metadata_Block#.40run-at - however,
        # QtWebEngine uses QWebEngineScript.InjectionPoint.Deferred (@run-at document-idle) as
        # default.
        #
        # NOTE that this needs to be done before setSourceCode, so that
        # QtWebEngine's parsing of GreaseMonkey tags will override it if there is a
        # @run-at comment.
        new_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)

        new_script.setSourceCode(script.code())
        new_script.setName(script.full_name())
        new_script.setRunsOnSubFrames(script.runs_on_sub_frames)

        if script.needs_document_end_workaround():
            log.greasemonkey.debug(
                f"Forcing @run-at document-end for {script.name}")
            new_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)

        log.greasemonkey.debug(f'adding script: {new_script.name()}')
        profile_scripts.insert(new_script)


@dataclasses.dataclass
class _Quirk:

    filename: str
    injection_point: QWebEngineScript.InjectionPoint = (
        QWebEngineScript.InjectionPoint.DocumentCreation)
    world: QWebEngineScript.ScriptWorldId = QWebEngineScript.ScriptWorldId.MainWorld
    predicate: bool = True
    name: Optional[str] = None

    def __post_init__(self):
        if self.name is None:
            self.name = f"js-{self.filename.replace('_', '-')}"


def _get_quirks():
    """Get a list of all available JS quirks."""
    versions = version.qtwebengine_versions()
    return [
        # FIXME:qt6 Double check which of those are still required
        _Quirk(
            'whatsapp_web',
            injection_point=QWebEngineScript.InjectionPoint.DocumentReady,
            world=QWebEngineScript.ScriptWorldId.ApplicationWorld,
        ),
        _Quirk('discord'),
        _Quirk(
            'googledocs',
            # will be an UA quirk once we set the JS UA as well
            name='ua-googledocs',
        ),

        _Quirk(
            'string_replaceall',
            predicate=versions.webengine < utils.VersionNumber(5, 15, 3),
        ),
        _Quirk(
            'array_at',
            predicate=versions.webengine < utils.VersionNumber(6, 3),
        ),
    ]


def _inject_site_specific_quirks(scripts):
    """Add site-specific quirk scripts."""
    if not config.val.content.site_specific_quirks.enabled:
        return

    for quirk in _get_quirks():
        if not quirk.predicate:
            continue
        src = resources.read_file(f'javascript/quirks/{quirk.filename}.user.js')
        if quirk.name not in config.val.content.site_specific_quirks.skip:
            scripts.insert(_script_factory(
                f'quirk_{quirk.filename}',
                src,
                world=quirk.world,
                injection_point=quirk.injection_point,
            ))


def _init_scripts_for_profile(profile: QWebEngineProfile) -> None:
    scripts = profile.scripts()

    # Early global scripts
    js_code = javascript.wrap_global(
        'scripts',
        resources.read_file('javascript/scroll.js'),
        resources.read_file('javascript/webelem.js'),
        resources.read_file('javascript/caret.js'),
    )
    # FIXME:qtwebengine what about subframes=True?
    scripts.insert(_script_factory('js', js_code, subframes=True))

    _inject_stylesheet(scripts)
    config.instance.changed.connect(
        functools.partial(
            _stylesheet_option_changed,
            profile,
        )
    )

    greasemonkey.gm_manager.scripts_reloaded.connect(
        functools.partial(
            _inject_all_greasemonkey_scripts,
            profile,
        )
    )
    _inject_all_greasemonkey_scripts(profile)

    _inject_site_specific_quirks(scripts)


def _init_profile(profile: QWebEngineProfile) -> None:
    """Initialize a new QWebEngineProfile.

    This currently only contains the steps which are shared between a private and a
    non-private profile (at the moment, only the default profile).
    """
    # FIXME:mypy subclass QWebEngineProfile instead?
    profile.setter = ProfileSetter(profile)  # type: ignore[attr-defined]
    profile.setter.init_profile()  # type: ignore[attr-defined]

    _qute_scheme_handler.install(profile)
    _req_interceptor.install(profile)
    _download_manager.install(profile)
    cookies.install_filter(profile)

    if notification.bridge is not None:
        notification.bridge.install(profile)

    # Clear visited links on web history clear
    history.web_history.history_cleared.connect(profile.clearAllVisitedLinks)
    history.web_history.url_cleared.connect(
        lambda url: profile.clearVisitedLinks([url]))

    _global_settings.init_settings()

    _init_scripts_for_profile(profile)


def _init_default_profile():
    """Init the default QWebEngineProfile."""
    global default_profile

    if machinery.IS_QT6:
        default_profile = QWebEngineProfile("Default")
    else:
        default_profile = QWebEngineProfile.defaultProfile()
    assert not default_profile.isOffTheRecord()

    assert parsed_user_agent is None  # avoid earlier profile initialization
    non_ua_version = version.qtwebengine_versions(avoid_init=True)

    init_user_agent()
    ua_version = version.qtwebengine_versions()
    if ua_version.webengine != non_ua_version.webengine:
        log.init.warning(
            "QtWebEngine version mismatch - unexpected behavior might occur, "
            "please open a bug about this.\n"
            f"  Early version: {non_ua_version}\n"
            f"  Real version:  {ua_version}")

    default_profile.setCachePath(
        os.path.join(standarddir.cache(), 'webengine'))
    default_profile.setPersistentStoragePath(
        os.path.join(standarddir.data(), 'webengine'))

    _init_profile(default_profile)


def init_private_profile():
    """Init the private QWebEngineProfile."""
    global private_profile

    if qtutils.is_single_process():
        return

    private_profile = QWebEngineProfile()
    assert private_profile.isOffTheRecord()
    _init_profile(private_profile)


def _init_site_specific_quirks():
    """Add custom user-agent settings for problematic sites.

    See https://github.com/qutebrowser/qutebrowser/issues/4810
    """
    if not config.val.content.site_specific_quirks.enabled:
        return

    # Please leave this here as a template for new UAs.
    # default_ua = ("Mozilla/5.0 ({os_info}) "
    #               "AppleWebKit/{webkit_version} (KHTML, like Gecko) "
    #               "{qt_key}/{qt_version} "
    #               "{upstream_browser_key}/{upstream_browser_version} "
    #               "Safari/{webkit_version}")
    no_qtwe_ua = ("Mozilla/5.0 ({os_info}) "
                  "AppleWebKit/{webkit_version} (KHTML, like Gecko) "
                  "{upstream_browser_key}/{upstream_browser_version} "
                  "Safari/{webkit_version}")
    new_chrome_ua = ("Mozilla/5.0 ({os_info}) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/99 "
                     "Safari/537.36")
    firefox_ua = "Mozilla/5.0 ({os_info}; rv:90.0) Gecko/20100101 Firefox/90.0"

    user_agents = [
        # Needed to avoid a ""WhatsApp works with Google Chrome 36+" error
        # page which doesn't allow to use WhatsApp Web at all. Also see the
        # additional JS quirk: qutebrowser/javascript/quirks/whatsapp_web.user.js
        # https://github.com/qutebrowser/qutebrowser/issues/4445
        ("ua-whatsapp", 'https://web.whatsapp.com/', no_qtwe_ua),

        # Needed to avoid a "you're using a browser [...] that doesn't allow us
        # to keep your account secure" error.
        # https://github.com/qutebrowser/qutebrowser/issues/5182
        ("ua-google", 'https://accounts.google.com/*', firefox_ua),

        # Needed because Slack adds an error which prevents using it relatively
        # aggressively, despite things actually working fine.
        # September 2020: Qt 5.12 works, but Qt <= 5.11 shows the error.
        # FIXME:qt6 Still needed?
        # https://github.com/qutebrowser/qutebrowser/issues/4669
        ("ua-slack", 'https://*.slack.com/*', new_chrome_ua),
    ]

    for name, pattern, ua in user_agents:
        if name not in config.val.content.site_specific_quirks.skip:
            config.instance.set_obj('content.headers.user_agent', ua,
                                    pattern=urlmatch.UrlPattern(pattern),
                                    hide_userconfig=True)

    if 'misc-krunker' not in config.val.content.site_specific_quirks.skip:
        config.instance.set_obj(
            'content.headers.accept_language',
            '',
            pattern=urlmatch.UrlPattern('https://matchmaker.krunker.io/*'),
            hide_userconfig=True,
        )


def _init_default_settings():
    """Set permissions required for internal functionality.

    - Make sure the devtools always get images/JS permissions.
    - On Qt 6, make sure files in the data path can load external resources.
    """
    devtools_settings: List[Tuple[str, Any]] = [
        ('content.javascript.enabled', True),
        ('content.images', True),
        ('content.cookies.accept', 'all'),
    ]

    for setting, value in devtools_settings:
        for pattern in ['chrome-devtools://*', 'devtools://*']:
            config.instance.set_obj(setting, value,
                                    pattern=urlmatch.UrlPattern(pattern),
                                    hide_userconfig=True)

    if machinery.IS_QT6:
        userscripts_settings: List[Tuple[str, Any]] = [
            ("content.local_content_can_access_remote_urls", True),
            ("content.local_content_can_access_file_urls", False),
        ]
        # https://codereview.qt-project.org/c/qt/qtwebengine/+/375672
        url = pathlib.Path(standarddir.data(), "userscripts").as_uri()
        for setting, value in userscripts_settings:
            config.instance.set_obj(setting,
                                    value,
                                    pattern=urlmatch.UrlPattern(f"{url}/*"),
                                    hide_userconfig=True)


def init():
    """Initialize the global QWebSettings."""
    webenginequtescheme.init()
    spell.init()

    # For some reason we need to keep a reference, otherwise the scheme handler
    # won't work...
    # https://www.riverbankcomputing.com/pipermail/pyqt/2016-September/038075.html
    global _qute_scheme_handler
    app = QApplication.instance()
    log.init.debug("Initializing qute://* handler...")
    _qute_scheme_handler = webenginequtescheme.QuteSchemeHandler(parent=app)

    global _req_interceptor
    log.init.debug("Initializing request interceptor...")
    from qutebrowser.browser.webengine import interceptor
    _req_interceptor = interceptor.RequestInterceptor(parent=app)

    global _download_manager
    log.init.debug("Initializing QtWebEngine downloads...")
    _download_manager = webenginedownloads.DownloadManager(parent=app)
    objreg.register('webengine-download-manager', _download_manager)
    from qutebrowser.misc import quitter
    quitter.instance.shutting_down.connect(_download_manager.shutdown)

    log.init.debug("Initializing notification presenter...")
    notification.init()

    log.init.debug("Initializing global settings...")
    global _global_settings
    _global_settings = WebEngineSettings(_SettingsWrapper())

    log.init.debug("Initializing profiles...")
    _init_default_profile()
    init_private_profile()
    config.instance.changed.connect(_update_settings)

    log.init.debug("Misc initialization...")
    _init_site_specific_quirks()
    _init_default_settings()


def shutdown():
    pass
