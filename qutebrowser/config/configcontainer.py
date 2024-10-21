"""This file defines static types for the `c` variable in `config.py`.

This is auto-generated from the `scripts/dev/generate_config_types.py` file.

It is not intended to be used at runtime.

Example usage:
```py
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from qutebrowser.config.configfiles import ConfigAPI
    from qutebrowser.config.configcontainer import ConfigContainer

    # note: these expressions aren't executed at runtime
    c = cast(ConfigContainer, ...)
    config = cast(ConfigAPI, ...)
```
"""

# pylint: disable=line-too-long, invalid-name

from __future__ import annotations
import re
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Optional, Union, Literal


@dataclass
class ConfigContainer:
    """Type for the `c` variable in `config.py`."""

    aliases: Optional[Mapping[str, str]]
    """Aliases for commands.

    The keys of the given dictionary are the aliases, while the values are the commands they map to.
    """

    confirm_quit: list[Literal["always", "multiple-tabs", "downloads", "never"]]
    """Require a confirmation before quitting the application."""

    history_gap_interval: int
    """Maximum time (in minutes) between two history items for them to be considered being from the same browsing session.

    Items with less time between them are grouped when being displayed in `:history`. Use -1 to disable separation.
    """

    changelog_after_upgrade: Literal["major", "minor", "patch", "never"]
    """When to show a changelog after qutebrowser was upgraded."""

    search: _Search

    @dataclass
    class _Search:
        ignore_case: Literal["always", "never", "smart"]
        """When to find text on a page case-insensitively."""

        incremental: bool
        """Find text on a page incrementally, renewing the search for each typed character."""

        wrap: bool
        """Wrap around at the top and bottom of the page when advancing through text matches using `:search-next` and `:search-prev`."""

        wrap_messages: bool
        """Display messages when advancing through text matches at the top and bottom of the page, e.g. `Search hit TOP`."""

    new_instance_open_target: Literal[
        "tab", "tab-bg", "tab-silent", "tab-bg-silent", "window", "private-window"
    ]
    """How to open links in an existing instance if a new one is launched.

    This happens when e.g. opening a link from a terminal.

    See `new_instance_open_target_window` to customize in which window the link is opened in.
    """

    new_instance_open_target_window: Literal[
        "first-opened", "last-opened", "last-focused", "last-visible"
    ]
    """Which window to choose when opening links as new tabs.

    When `new_instance_open_target` is set to `window`, this is ignored.
    """

    session: _Session

    @dataclass
    class _Session:
        default_name: Optional[Optional[str]]
        """Name of the session to save by default.

        If this is set to null, the session which was last loaded is saved.
        """

        lazy_restore: bool
        """Load a restored tab as soon as it takes focus."""

    backend: Literal["webengine", "webkit"]
    """Backend to use to display websites.

    qutebrowser supports two different web rendering engines / backends, QtWebEngine and QtWebKit (not recommended).

    QtWebEngine is Qt's official successor to QtWebKit, and both the default/recommended backend. It's based on a stripped-down Chromium and regularly updated with security fixes and new features by the Qt project: https://wiki.qt.io/QtWebEngine

    QtWebKit was qutebrowser's original backend when the project was started. However, support for QtWebKit was discontinued by the Qt project with Qt 5.6 in 2016. The development of QtWebKit was picked up in an official fork: https://github.com/qtwebkit/qtwebkit - however, the project seems to have stalled again. The latest release (5.212.0 Alpha 4) from March 2020 is based on a WebKit version from 2016, with many known security vulnerabilities. Additionally, there is no process isolation and sandboxing. Due to all those issues, while support for QtWebKit is still available in qutebrowser for now, using it is strongly discouraged.
    """

    qt: _Qt

    @dataclass
    class _Qt:
        args: Optional[list[str]]
        """Additional arguments to pass to Qt, without leading `--`.

        With QtWebEngine, some Chromium arguments (see https://peter.sh/experiments/chromium-command-line-switches/ for a list) will work.
        """

        environ: Optional[Mapping[str, Optional[str]]]
        """Additional environment variables to set.

        Setting an environment variable to null/None will unset it.
        """

        force_software_rendering: Literal[
            "software-opengl", "qt-quick", "chromium", "none"
        ]
        """Force software rendering for QtWebEngine.

        This is needed for QtWebEngine to work with Nouveau drivers and can be useful in other scenarios related to graphic issues.
        """

        force_platform: Optional[Optional[str]]
        """Force a Qt platform to use.

        This sets the `QT_QPA_PLATFORM` environment variable and is useful to force using the XCB plugin when running QtWebEngine on Wayland.
        """

        force_platformtheme: Optional[Optional[str]]
        """Force a Qt platformtheme to use.

        This sets the `QT_QPA_PLATFORMTHEME` environment variable which controls dialogs like the filepicker. By default, Qt determines the platform theme based on the desktop environment.
        """

        chromium: _Chromium

        @dataclass
        class _Chromium:
            process_model: Literal[
                "process-per-site-instance", "process-per-site", "single-process"
            ]
            """Which Chromium process model to use.

            Alternative process models use less resources, but decrease security and robustness.

            See the following pages for more details:



              - https://www.chromium.org/developers/design-documents/process-models

              - https://doc.qt.io/qt-6/qtwebengine-features.html#process-models
            """

            low_end_device_mode: Literal["always", "auto", "never"]
            """When to use Chromium's low-end device mode.

            This improves the RAM usage of renderer processes, at the expense of performance.
            """

            sandboxing: Literal["enable-all", "disable-seccomp-bpf", "disable-all"]
            """What sandboxing mechanisms in Chromium to use.

            Chromium has various sandboxing layers, which should be enabled for normal browser usage. Mainly for testing and development, it's possible to disable individual sandboxing layers via this setting.

            Open `chrome://sandbox` to see the current sandbox status.

            Changing this setting is only recommended if you know what you're doing, as it **disables one of Chromium's security layers**. To avoid sandboxing being accidentally disabled persistently, this setting can only be set via `config.py`, not via `:set`.

            See the Chromium documentation for more details:

            - https://chromium.googlesource.com/chromium/src/\\+/HEAD/docs/linux/sandboxing.md[Linux] - https://chromium.googlesource.com/chromium/src/\\+/HEAD/docs/design/sandbox.md[Windows] - https://chromium.googlesource.com/chromium/src/\\+/HEAD/docs/design/sandbox_faq.md[FAQ (Windows-centric)]
            """

            experimental_web_platform_features: Literal["always", "auto", "never"]
            """Enables Web Platform features that are in development.

            This passes the `--enable-experimental-web-platform-features` flag to Chromium. By default, this is enabled with Qt 5 to maximize compatibility despite an aging Chromium base.
            """

        highdpi: bool
        """Turn on Qt HighDPI scaling.

        This is equivalent to setting QT_ENABLE_HIGHDPI_SCALING=1 (Qt >= 5.14) in the environment.

        It's off by default as it can cause issues with some bitmap fonts. As an alternative to this, it's possible to set font sizes and the `zoom.default` setting.
        """

        workarounds: _Workarounds

        @dataclass
        class _Workarounds:
            remove_service_workers: bool
            """Delete the QtWebEngine Service Worker directory on every start.

            This workaround can help with certain crashes caused by an unknown QtWebEngine bug related to Service Workers. Those crashes happen seemingly immediately on Windows; after one hour of operation on other systems.

            Note however that enabling this option *can lead to data loss* on some pages (as Service Worker data isn't persisted) and will negatively impact start-up time.
            """

            locale: bool
            """Work around locale parsing issues in QtWebEngine 5.15.3.

            With some locales, QtWebEngine 5.15.3 is unusable without this workaround. In affected scenarios, QtWebEngine will log "Network service crashed, restarting service." and only display a blank page.

            However, It is expected that distributions shipping QtWebEngine 5.15.3 follow up with a proper fix soon, so it is disabled by default.
            """

            disable_accelerated_2d_canvas: Literal["always", "auto", "never"]
            """Disable accelerated 2d canvas to avoid graphical glitches.

            On some setups graphical issues can occur on sites like Google sheets and PDF.js. These don't occur when accelerated 2d canvas is turned off, so we do that by default.

            So far these glitches only occur on some Intel graphics devices.
            """

            disable_hangouts_extension: bool
            """Disable the Hangouts extension.

            The Hangouts extension provides additional APIs for Google domains only.

            Hangouts has been replaced with Meet, which appears to work without this extension.

            Note this setting gets ignored and the Hangouts extension is always disabled to avoid crashes on Qt 6.5.0 to 6.5.3 if dark mode is enabled, as well as on Qt 6.6.0.
            """

    auto_save: _AutoSave

    @dataclass
    class _AutoSave:
        interval: int
        """Time interval (in milliseconds) between auto-saves of config/cookies/etc."""

        session: bool
        """Always restore open sites when qutebrowser is reopened.

        Without this option set, `:wq` (`:quit --save`) needs to be used to save open tabs (and restore them), while quitting qutebrowser in any other way will not save/restore the session.

        By default, this will save to the session which was last loaded. This behavior can be customized via the `session.default_name` setting.
        """

    content: _Content

    @dataclass
    class _Content:
        autoplay: bool
        """Automatically start playing `<video>` elements."""

        cache: _Cache

        @dataclass
        class _Cache:
            size: Optional[Optional[int]]
            """Size (in bytes) of the HTTP network cache. Null to use the default value.

            With QtWebEngine, the maximum supported value is 2147483647 (~2 GB).
            """

            maximum_pages: int
            """Maximum number of pages to hold in the global memory page cache.

            The page cache allows for a nicer user experience when navigating forth or back to pages in the forward/back history, by pausing and resuming up to _n_ pages.

            For more information about the feature, please refer to: https://webkit.org/blog/427/webkit-page-cache-i-the-basics/
            """

            appcache: bool
            """Enable support for the HTML 5 web application cache feature.

            An application cache acts like an HTTP cache in some sense. For documents that use the application cache via JavaScript, the loader engine will first ask the application cache for the contents, before hitting the network.
            """

        canvas_reading: bool
        """Allow websites to read canvas elements.

        Note this is needed for some websites to work properly.

        On QtWebEngine < 6.6, this setting requires a restart and does not support URL patterns, only the global setting is applied.
        """

        cookies: _Cookies

        @dataclass
        class _Cookies:
            accept: Literal["all", "no-3rdparty", "no-unknown-3rdparty", "never"]
            """Which cookies to accept.

            With QtWebEngine, this setting also controls other features with tracking capabilities similar to those of cookies; including IndexedDB, DOM storage, filesystem API, service workers, and AppCache.

            Note that with QtWebKit, only `all` and `never` are supported as per-domain values. Setting `no-3rdparty` or `no-unknown-3rdparty` per-domain on QtWebKit will have the same effect as `all`.

            If this setting is used with URL patterns, the pattern gets applied to the origin/first party URL of the page making the request, not the request URL.

            With QtWebEngine 5.15.0+, paths will be stripped from URLs, so URL patterns using paths will not match. With QtWebEngine 5.15.2+, subdomains are additionally stripped as well, so you will typically need to set this setting for `example.com` when the cookie is set on `somesubdomain.example.com` for it to work properly.

            To debug issues with this setting, start qutebrowser with `--debug --logfilter network --debug-flag log-cookies` which will show all cookies being set.
            """

            store: bool
            """Store cookies."""

        default_encoding: str
        """Default encoding to use for websites.

        The encoding must be a string describing an encoding such as _utf-8_, _iso-8859-1_, etc.
        """

        unknown_url_scheme_policy: Literal[
            "disallow", "allow-from-user-interaction", "allow-all"
        ]
        """How navigation requests to URLs with unknown schemes are handled."""

        fullscreen: _Fullscreen

        @dataclass
        class _Fullscreen:
            window: bool
            """Limit fullscreen to the browser window (does not expand to fill the screen)."""

            overlay_timeout: int
            """Set fullscreen notification overlay timeout in milliseconds.

            If set to 0, no overlay will be displayed.
            """

        desktop_capture: bool
        """Allow websites to share screen content."""

        dns_prefetch: bool
        """Try to pre-fetch DNS entries to speed up browsing."""

        frame_flattening: bool
        """Expand each subframe to its contents.

        This will flatten all the frames to become one scrollable page.
        """

        prefers_reduced_motion: bool
        """Request websites to minimize non-essentials animations and motion.

        This results in the `prefers-reduced-motion` CSS media query to evaluate to `reduce` (rather than `no-preference`).

        On Windows, if this setting is set to False, the system-wide animation setting is considered.
        """

        site_specific_quirks: _SiteSpecificQuirks

        @dataclass
        class _SiteSpecificQuirks:
            enabled: bool
            """Enable quirks (such as faked user agent headers) needed to get specific sites to work properly."""

            skip: Optional[
                list[
                    Literal[
                        "ua-whatsapp",
                        "ua-google",
                        "ua-slack",
                        "ua-googledocs",
                        "js-whatsapp-web",
                        "js-discord",
                        "js-string-replaceall",
                        "js-array-at",
                        "misc-krunker",
                        "misc-mathml-darkmode",
                    ]
                ]
            ]
            """Disable a list of named quirks."""

        geolocation: bool
        """Allow websites to request geolocations."""

        mouse_lock: bool
        """Allow websites to lock your mouse pointer."""

        headers: _Headers

        @dataclass
        class _Headers:
            accept_language: Optional[str]
            """Value to send in the `Accept-Language` header.

            Note that the value read from JavaScript is always the global value.
            """

            custom: Optional[Mapping[str, Optional[str]]]
            """Custom headers for qutebrowser HTTP requests."""

            do_not_track: Optional[bool]
            """Value to send in the `DNT` header.

            When this is set to true, qutebrowser asks websites to not track your identity. If set to null, the DNT header is not sent at all.
            """

            referer: Literal["always", "never", "same-domain"]
            """When to send the Referer header.

            The Referer header tells websites from which website you were coming from when visiting them. Note that with QtWebEngine, websites can override this preference by setting the `Referrer-Policy:` header, so that any websites visited from them get the full referer.

            No restart is needed with QtWebKit.
            """

            user_agent: str
            """User agent to send.



            The following placeholders are defined:



            * `{os_info}`: Something like "X11; Linux x86_64".

            * `{webkit_version}`: The underlying WebKit version (set to a fixed value

              with QtWebEngine).

            * `{qt_key}`: "Qt" for QtWebKit, "QtWebEngine" for QtWebEngine.

            * `{qt_version}`: The underlying Qt version.

            * `{upstream_browser_key}`: "Version" for QtWebKit, "Chrome" for

              QtWebEngine.

            * `{upstream_browser_version}`: The corresponding Safari/Chrome version.

            * `{qutebrowser_version}`: The currently running qutebrowser version.



            The default value is equal to the unchanged user agent of

            QtWebKit/QtWebEngine.



            Note that the value read from JavaScript is always the global value. With

            QtWebEngine between 5.12 and 5.14 (inclusive), changing the value exposed

            to JavaScript requires a restart.


            """

        blocking: _Blocking

        @dataclass
        class _Blocking:
            enabled: bool
            """Enable the ad/host blocker"""

            hosts: _Hosts

            @dataclass
            class _Hosts:
                lists: Optional[list[str]]
                """List of URLs to host blocklists for the host blocker.



                Only used when the simple host-blocker is used (see `content.blocking.method`).



                The file can be in one of the following formats:



                - An `/etc/hosts`-like file

                - One host per line

                - A zip-file of any of the above, with either only one file, or a file

                  named `hosts` (with any extension).



                It's also possible to add a local file or directory via a `file://` URL. In

                case of a directory, all files in the directory are read as adblock lists.



                The file `~/.config/qutebrowser/blocked-hosts` is always read if it exists.


                """

                block_subdomains: bool
                """Block subdomains of blocked hosts.

                Note: If only a single subdomain is blocked but should be allowed, consider using `content.blocking.whitelist` instead.
                """

            method: Literal["auto", "adblock", "hosts", "both"]
            """Which method of blocking ads should be used.



            Support for Adblock Plus (ABP) syntax blocklists using Brave's Rust library requires

            the `adblock` Python package to be installed, which is an optional dependency of

            qutebrowser. It is required when either `adblock` or `both` are selected.


            """

            adblock: _Adblock

            @dataclass
            class _Adblock:
                lists: Optional[list[str]]
                """List of URLs to ABP-style adblocking rulesets.



                Only used when Brave's ABP-style adblocker is used (see `content.blocking.method`).



                You can find an overview of available lists here:

                https://adblockplus.org/en/subscriptions - note that the special

                `subscribe.adblockplus.org` links aren't handled by qutebrowser, you will instead

                need to find the link to the raw `.txt` file (e.g. by extracting it from the

                `location` parameter of the subscribe URL and URL-decoding it).


                """

            whitelist: Optional[list[str]]
            """A list of patterns that should always be loaded, despite being blocked by the ad-/host-blocker.

            Local domains are always exempt from adblocking.

            Note this whitelists otherwise blocked requests, not first-party URLs. As an example, if `example.org` loads an ad from `ads.example.org`, the whitelist entry could be `https://ads.example.org/*`. If you want to disable the adblocker on a given page, use the `content.blocking.enabled` setting with a URL pattern instead.
            """

        hyperlink_auditing: bool
        """Enable hyperlink auditing (`<a ping>`)."""

        images: bool
        """Load images automatically in web pages."""

        javascript: _Javascript

        @dataclass
        class _Javascript:
            alert: bool
            """Show javascript alerts."""

            clipboard: Literal["none", "access", "access-paste"]
            """Allow JavaScript to read from or write to the clipboard.

            With QtWebEngine, writing the clipboard as response to a user interaction is always allowed.
            """

            can_close_tabs: bool
            """Allow JavaScript to close tabs."""

            can_open_tabs_automatically: bool
            """Allow JavaScript to open new tabs without user interaction."""

            enabled: bool
            """Enable JavaScript."""

            log: Mapping[str, Literal["none", "debug", "info", "warning", "error"]]
            """Log levels to use for JavaScript console logging messages.

            When a JavaScript message with the level given in the dictionary key is logged, the corresponding dictionary value selects the qutebrowser logger to use.

            On QtWebKit, the "unknown" setting is always used.

            The following levels are valid: `none`, `debug`, `info`, `warning`, `error`.
            """

            log_message: _LogMessage

            @dataclass
            class _LogMessage:
                levels: Optional[
                    Mapping[str, Optional[list[Literal["info", "warning", "error"]]]]
                ]
                """Javascript message sources/levels to show in the qutebrowser UI.

                When a JavaScript message is logged from a location matching the glob pattern given in the key, and is from one of the levels listed as value, it's surfaced as a message in the qutebrowser UI.

                By default, errors happening in qutebrowser internally are shown to the user.
                """

                excludes: Optional[Mapping[str, list[str]]]
                """Javascript messages to *not* show in the UI, despite a corresponding `content.javascript.log_message.levels` setting.

                Both keys and values are glob patterns, with the key matching the location of the error, and the value matching the error message.

                By default, the https://web.dev/csp/[Content security policy] violations triggered by qutebrowser's stylesheet handling are excluded, as those errors are to be expected and can't be easily handled by the underlying code.
                """

            modal_dialog: bool
            """Use the standard JavaScript modal dialog for `alert()` and `confirm()`."""

            prompt: bool
            """Show javascript prompts."""

            legacy_touch_events: Literal["always", "auto", "never"]
            """Enables the legacy touch event feature.

            This affects JS APIs such as:

            - ontouch* members on window, document, Element - document.createTouch, document.createTouchList - document.createEvent("TouchEvent")

            Newer Chromium versions have those disabled by default: https://bugs.chromium.org/p/chromium/issues/detail?id=392584 https://groups.google.com/a/chromium.org/g/blink-dev/c/KV6kqDJpYiE
            """

        local_content_can_access_remote_urls: bool
        """Allow locally loaded documents to access remote URLs."""

        local_content_can_access_file_urls: bool
        """Allow locally loaded documents to access other local URLs."""

        local_storage: bool
        """Enable support for HTML 5 local storage and Web SQL."""

        media: _Media

        @dataclass
        class _Media:
            audio_capture: bool
            """Allow websites to record audio."""

            audio_video_capture: bool
            """Allow websites to record audio and video."""

            video_capture: bool
            """Allow websites to record video."""

        netrc_file: Optional[Optional[str]]
        """Netrc-file for HTTP authentication.

        If unset, `~/.netrc` is used.
        """

        notifications: _Notifications

        @dataclass
        class _Notifications:
            enabled: bool
            """Allow websites to show notifications."""

            presenter: Literal[
                "auto", "qt", "libnotify", "systray", "messages", "herbe"
            ]
            """What notification presenter to use for web notifications.

            Note that not all implementations support all features of notifications:

            - The `qt` and `systray` options only support showing one notification at the time

              and ignore the `tag` option to replace existing notifications.

            - The `herbe` option only supports showing one notification at the time and doesn't

              show icons.

            - The `messages` option doesn't show icons and doesn't support the `click` and

              `close` events.
            """

            show_origin: bool
            """Whether to show the origin URL for notifications.

            Note that URL patterns with this setting only get matched against the origin part of the URL, so e.g. paths in patterns will never match.

            Note that with the `qt` presenter, origins are never shown.
            """

        pdfjs: bool
        """Display PDF files via PDF.js in the browser without showing a download prompt.

        Note that the files can still be downloaded by clicking the download button in the pdf.js viewer. With this set to `false`, the `:prompt-open-download --pdfjs` command (bound to `<Ctrl-p>` by default) can be used in the download prompt.
        """

        persistent_storage: bool
        """Allow websites to request persistent storage quota via `navigator.webkitPersistentStorage.requestQuota`."""

        plugins: bool
        """Enable plugins in Web pages."""

        print_element_backgrounds: bool
        """Draw the background color and images also when the page is printed."""

        private_browsing: bool
        """Open new windows in private browsing mode which does not record visited pages."""

        proxy: Literal["system", "none"]
        """Proxy to use.

        In addition to the listed values, you can use a `socks://...` or `http://...` URL.

        Note that with QtWebEngine, it will take a couple of seconds until the change is applied, if this value is changed at runtime. Authentication for SOCKS proxies isn't supported due to Chromium limitations.
        """

        proxy_dns_requests: bool
        """Send DNS requests over the configured proxy."""

        register_protocol_handler: bool
        """Allow websites to register protocol handlers via `navigator.registerProtocolHandler`."""

        tls: _Tls

        @dataclass
        class _Tls:
            certificate_errors: Literal[
                "ask", "ask-block-thirdparty", "block", "load-insecurely"
            ]
            """How to proceed on TLS certificate errors."""

        user_stylesheets: Optional[Union[str, Optional[list[str]]]]
        """List of user stylesheet filenames to use."""

        webgl: bool
        """Enable WebGL."""

        webrtc_ip_handling_policy: Literal[
            "all-interfaces",
            "default-public-and-private-interfaces",
            "default-public-interface-only",
            "disable-non-proxied-udp",
        ]
        """Which interfaces to expose via WebRTC."""

        xss_auditing: bool
        """Monitor load requests for cross-site scripting attempts.

        Suspicious scripts will be blocked and reported in the devtools JavaScript console.

        Note that bypasses for the XSS auditor are widely known and it can be abused for cross-site info leaks in some scenarios, see: https://www.chromium.org/developers/design-documents/xss-auditor
        """

        mute: bool
        """Automatically mute tabs.

        Note that if the `:tab-mute` command is used, the mute status for the affected tab is now controlled manually, and this setting doesn't have any effect.
        """

    completion: _Completion

    @dataclass
    class _Completion:
        cmd_history_max_items: int
        """Number of commands to save in the command history.

        0: no history / -1: unlimited
        """

        height: Union[int, str]
        """Height (in pixels or as percentage of the window) of the completion."""

        quick: bool
        """Move on to the next part when there's only one possible completion left."""

        show: Literal["always", "auto", "never"]
        """When to show the autocompletion window."""

        shrink: bool
        """Shrink the completion to be smaller than the configured size if there are no scrollbars."""

        scrollbar: _Scrollbar

        @dataclass
        class _Scrollbar:
            width: int
            """Width (in pixels) of the scrollbar in the completion window."""

            padding: int
            """Padding (in pixels) of the scrollbar handle in the completion window."""

        timestamp_format: Optional[str]
        """Format of timestamps (e.g. for the history completion).

        See https://sqlite.org/lang_datefunc.html and https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior for allowed substitutions, qutebrowser uses both sqlite and Python to format its timestamps.
        """

        web_history: _WebHistory

        @dataclass
        class _WebHistory:
            exclude: Optional[list[str]]
            """A list of patterns which should not be shown in the history.

            This only affects the completion. Matching URLs are still saved in the history (and visible on the `:history` page), but hidden in the completion.

            Changing this setting will cause the completion history to be regenerated on the next start, which will take a short while.
            """

            max_items: int
            """Number of URLs to show in the web history.

            0: no history / -1: unlimited
            """

        delay: int
        """Delay (in milliseconds) before updating completions after typing a character."""

        min_chars: int
        """Minimum amount of characters needed to update completions."""

        use_best_match: bool
        """Execute the best-matching command on a partial match."""

        open_categories: Optional[
            list[
                Literal[
                    "searchengines", "quickmarks", "bookmarks", "history", "filesystem"
                ]
            ]
        ]
        """Which categories to show (in which order) in the :open completion."""

        favorite_paths: Optional[list[str]]
        """Default filesystem autocomplete suggestions for :open.

        The elements of this list show up in the completion window under the Filesystem category when the command line contains `:open` but no argument.
        """

    downloads: _Downloads

    @dataclass
    class _Downloads:
        location: _Location

        @dataclass
        class _Location:
            directory: Optional[Optional[str]]
            """Directory to save downloads to.

            If unset, a sensible OS-specific default is used.
            """

            prompt: bool
            """Prompt the user for the download location.

            If set to false, `downloads.location.directory` will be used.
            """

            remember: bool
            """Remember the last used download directory."""

            suggestion: Literal["path", "filename", "both"]
            """What to display in the download filename input."""

        open_dispatcher: Optional[Optional[str]]
        """Default program used to open downloads.

        If null, the default internal handler is used.

        Any `{}` in the string will be expanded to the filename, else the filename will be appended.
        """

        position: Literal["top", "bottom"]
        """Where to show the downloaded files."""

        prevent_mixed_content: bool
        """Automatically abort insecure (HTTP) downloads originating from secure (HTTPS) pages.

        For per-domain settings, the relevant URL is the URL initiating the download, not the URL the download itself is coming from. It's not recommended to set this setting to false globally.
        """

        remove_finished: int
        """Duration (in milliseconds) to wait before removing finished downloads.

        If set to -1, downloads are never removed.
        """

    editor: _Editor

    @dataclass
    class _Editor:
        command: list[str]
        """Editor (and arguments) to use for the `edit-*` commands.

        The following placeholders are defined:



        * `{file}`: Filename of the file to be edited.

        * `{line}`: Line in which the caret is found in the text.

        * `{column}`: Column in which the caret is found in the text.

        * `{line0}`: Same as `{line}`, but starting from index 0.

        * `{column0}`: Same as `{column}`, but starting from index 0.


        """

        encoding: str
        """Encoding to use for the editor."""

        remove_file: bool
        """Delete the temporary file upon closing the editor."""

    fileselect: _Fileselect

    @dataclass
    class _Fileselect:
        handler: Literal["default", "external"]
        """Handler for selecting file(s) in forms. If `external`, then the commands specified by `fileselect.single_file.command`, `fileselect.multiple_files.command` and `fileselect.folder.command` are used to select one file, multiple files, and folders, respectively."""

        single_file: _SingleFile

        @dataclass
        class _SingleFile:
            command: list[str]
            """Command (and arguments) to use for selecting a single file in forms. The command should write the selected file path to the specified file or stdout.

            The following placeholders are defined:

            * `{}`: Filename of the file to be written to. If not contained in any argument, the

              standard output of the command is read instead.
            """

        multiple_files: _MultipleFiles

        @dataclass
        class _MultipleFiles:
            command: list[str]
            """Command (and arguments) to use for selecting multiple files in forms. The command should write the selected file paths to the specified file or to stdout, separated by newlines.

            The following placeholders are defined:

            * `{}`: Filename of the file to be written to. If not contained in any argument, the

              standard output of the command is read instead.
            """

        folder: _Folder

        @dataclass
        class _Folder:
            command: list[str]
            """Command (and arguments) to use for selecting a single folder in forms. The command should write the selected folder path to the specified file or stdout.

            The following placeholders are defined:

            * `{}`: Filename of the file to be written to. If not contained in any argument, the

              standard output of the command is read instead.
            """

    hints: _Hints

    @dataclass
    class _Hints:
        auto_follow: Literal["always", "unique-match", "full-match", "never"]
        """When a hint can be automatically followed without pressing Enter."""

        auto_follow_timeout: int
        """Duration (in milliseconds) to ignore normal-mode key bindings after a successful auto-follow."""

        border: str
        """CSS border value for hints."""

        padding: Mapping[str, int]
        """Padding (in pixels) for hints."""

        radius: int
        """Rounding radius (in pixels) for the edges of hints."""

        chars: str
        """Characters used for hint strings."""

        dictionary: str
        """Dictionary file to be used by the word hints."""

        find_implementation: Literal["javascript", "python"]
        """Which implementation to use to find elements to hint."""

        hide_unmatched_rapid_hints: bool
        """Hide unmatched hints in rapid mode."""

        min_chars: int
        """Minimum number of characters used for hint strings."""

        mode: Literal["number", "letter", "word"]
        """Mode to use for hints."""

        next_regexes: list[Union[str, re.Pattern[str]]]
        """Comma-separated list of regular expressions to use for 'next' links."""

        prev_regexes: list[Union[str, re.Pattern[str]]]
        """Comma-separated list of regular expressions to use for 'prev' links."""

        scatter: bool
        """Scatter hint key chains (like Vimium) or not (like dwb).

        Ignored for number hints.
        """

        selectors: Mapping[str, Optional[list[str]]]
        """CSS selectors used to determine which elements on a page should have hints."""

        uppercase: bool
        """Make characters in hint strings uppercase."""

        leave_on_load: bool
        """Leave hint mode when starting a new page load."""

    input: _Input

    @dataclass
    class _Input:
        escape_quits_reporter: bool
        """Allow Escape to quit the crash reporter."""

        forward_unbound_keys: Literal["all", "auto", "none"]
        """Which unbound keys to forward to the webview in normal mode."""

        insert_mode: _InsertMode

        @dataclass
        class _InsertMode:
            auto_load: bool
            """Automatically enter insert mode if an editable element is focused after loading the page."""

            auto_enter: bool
            """Enter insert mode if an editable element is clicked."""

            auto_leave: bool
            """Leave insert mode if a non-editable element is clicked."""

            plugins: bool
            """Switch to insert mode when clicking flash and other plugins."""

            leave_on_load: bool
            """Leave insert mode when starting a new page load.

            Patterns may be unreliable on this setting, and they may match the url you are navigating to, or the URL you are navigating from.
            """

        links_included_in_focus_chain: bool
        """Include hyperlinks in the keyboard focus chain when tabbing."""

        mouse: _Mouse

        @dataclass
        class _Mouse:
            back_forward_buttons: bool
            """Enable back and forward buttons on the mouse."""

            rocker_gestures: bool
            """Enable Opera-like mouse rocker gestures.

            This disables the context menu.
            """

        partial_timeout: int
        """Timeout (in milliseconds) for partially typed key bindings.

        If the current input forms only partial matches, the keystring will be cleared after this time.

        If set to 0, partially typed bindings are never cleared.
        """

        spatial_navigation: bool
        """Enable spatial navigation.

        Spatial navigation consists in the ability to navigate between focusable elements, such as hyperlinks and form controls, on a web page by using the Left, Right, Up and Down arrow keys. For example, if a user presses the Right key, heuristics determine whether there is an element they might be trying to reach towards the right and which element they probably want.
        """

        media_keys: bool
        """Whether the underlying Chromium should handle media keys.

        On Linux, disabling this also disables Chromium's MPRIS integration.
        """

        match_counts: bool
        """Interpret number prefixes as counts for bindings.

        This enables for vi-like bindings that can be prefixed with a number to indicate a count. Disabling it allows for emacs-like bindings where number keys are passed through (according to `input.forward_unbound_keys`) instead.
        """

        mode_override: Optional[Optional[Literal["normal", "insert", "passthrough"]]]
        """Mode to change to when focusing on a tab/URL changes."""

    keyhint: _Keyhint

    @dataclass
    class _Keyhint:
        blacklist: Optional[list[str]]
        """Keychains that shouldn't be shown in the keyhint dialog.

        Globs are supported, so `;*` will blacklist all keychains starting with `;`. Use `*` to disable keyhints.
        """

        radius: int
        """Rounding radius (in pixels) for the edges of the keyhint dialog."""

        delay: int
        """Time (in milliseconds) from pressing a key to seeing the keyhint dialog."""

    messages: _Messages

    @dataclass
    class _Messages:
        timeout: int
        """Duration (in milliseconds) to show messages in the statusbar for.

        Set to 0 to never clear messages.
        """

    prompt: _Prompt

    @dataclass
    class _Prompt:
        filebrowser: bool
        """Show a filebrowser in download prompts."""

        radius: int
        """Rounding radius (in pixels) for the edges of prompts."""

    scrolling: _Scrolling

    @dataclass
    class _Scrolling:
        bar: Literal["always", "never", "when-searching", "overlay"]
        """When/how to show the scrollbar."""

        smooth: bool
        """Enable smooth scrolling for web pages.

        Note smooth scrolling does not work with the `:scroll-px` command.
        """

    spellcheck: _Spellcheck

    @dataclass
    class _Spellcheck:
        languages: Optional[
            list[
                Literal[
                    "af-ZA",
                    "bg-BG",
                    "ca-ES",
                    "cs-CZ",
                    "da-DK",
                    "de-DE",
                    "el-GR",
                    "en-AU",
                    "en-CA",
                    "en-GB",
                    "en-US",
                    "es-ES",
                    "et-EE",
                    "fa-IR",
                    "fo-FO",
                    "fr-FR",
                    "he-IL",
                    "hi-IN",
                    "hr-HR",
                    "hu-HU",
                    "id-ID",
                    "it-IT",
                    "ko",
                    "lt-LT",
                    "lv-LV",
                    "nb-NO",
                    "nl-NL",
                    "pl-PL",
                    "pt-BR",
                    "pt-PT",
                    "ro-RO",
                    "ru-RU",
                    "sh",
                    "sk-SK",
                    "sl-SI",
                    "sq",
                    "sr",
                    "sv-SE",
                    "ta-IN",
                    "tg-TG",
                    "tr-TR",
                    "uk-UA",
                    "vi-VN",
                ]
            ]
        ]
        """Languages to use for spell checking.

        You can check for available languages and install dictionaries using scripts/dictcli.py. Run the script with -h/--help for instructions.
        """

    statusbar: _Statusbar

    @dataclass
    class _Statusbar:
        show: Literal["always", "never", "in-mode"]
        """When to show the statusbar."""

        padding: Mapping[str, int]
        """Padding (in pixels) for the statusbar."""

        position: Literal["top", "bottom"]
        """Position of the status bar."""

        widgets: Optional[
            list[
                Literal[
                    "url",
                    "scroll",
                    "scroll_raw",
                    "history",
                    "search_match",
                    "tabs",
                    "keypress",
                    "progress",
                    "text:foo",
                    "clock",
                ]
            ]
        ]
        """List of widgets displayed in the statusbar."""

    tabs: _Tabs

    @dataclass
    class _Tabs:
        background: bool
        """Open new tabs (middleclick/ctrl+click) in the background."""

        close_mouse_button: Literal["right", "middle", "none"]
        """Mouse button with which to close tabs."""

        close_mouse_button_on_bar: Literal[
            "new-tab", "close-current", "close-last", "ignore"
        ]
        """How to behave when the close mouse button is pressed on the tab bar."""

        favicons: _Favicons

        @dataclass
        class _Favicons:
            scale: float
            """Scaling factor for favicons in the tab bar.

            The tab size is unchanged, so big favicons also require extra `tabs.padding`.
            """

            show: Literal["always", "never", "pinned"]
            """When to show favicons in the tab bar.

            When switching this from never to always/pinned, note that favicons might not be loaded yet, thus tabs might require a reload to display them.
            """

        last_close: Literal["ignore", "blank", "startpage", "default-page", "close"]
        """How to behave when the last tab is closed.

        If the `tabs.tabs_are_windows` setting is set, this is ignored and the behavior is always identical to the `close` value.
        """

        mousewheel_switching: bool
        """Switch between tabs using the mouse wheel."""

        new_position: _NewPosition

        @dataclass
        class _NewPosition:
            related: Literal["prev", "next", "first", "last"]
            """Position of new tabs opened from another tab.

            See `tabs.new_position.stacking` for controlling stacking behavior.
            """

            unrelated: Literal["prev", "next", "first", "last"]
            """Position of new tabs which are not opened from another tab.

            See `tabs.new_position.stacking` for controlling stacking behavior.
            """

            stacking: bool
            """Stack related tabs on top of each other when opened consecutively.

            Only applies for `next` and `prev` values of `tabs.new_position.related` and `tabs.new_position.unrelated`.
            """

        padding: Mapping[str, int]
        """Padding (in pixels) around text for tabs."""

        mode_on_change: Literal["persist", "restore", "normal"]
        """When switching tabs, what input mode is applied."""

        position: Literal["top", "bottom", "left", "right"]
        """Position of the tab bar."""

        select_on_remove: Literal["prev", "next", "last-used"]
        """Which tab to select when the focused tab is removed."""

        show: Literal["always", "never", "multiple", "switching"]
        """When to show the tab bar."""

        show_switching_delay: int
        """Duration (in milliseconds) to show the tab bar before hiding it when tabs.show is set to 'switching'."""

        tabs_are_windows: bool
        """Open a new window for every tab."""

        title: _Title

        @dataclass
        class _Title:
            alignment: Literal["left", "right", "center"]
            """Alignment of the text inside of tabs."""

            elide: Literal["left", "right", "middle", "none"]
            """Position of ellipsis in truncated title of tabs."""

            format: Optional[str]
            """Format to use for the tab title.

            The following placeholders are defined:



            * `{perc}`: Percentage as a string like `[10%]`.

            * `{perc_raw}`: Raw percentage, e.g. `10`.

            * `{current_title}`: Title of the current web page.

            * `{title_sep}`: The string `" - "` if a title is set, empty otherwise.

            * `{index}`: Index of this tab.

            * `{aligned_index}`: Index of this tab padded with spaces to have the same

              width.

            * `{relative_index}`: Index of this tab relative to the current tab.

            * `{id}`: Internal tab ID of this tab.

            * `{scroll_pos}`: Page scroll position.

            * `{host}`: Host of the current web page.

            * `{backend}`: Either `webkit` or `webengine`

            * `{private}`: Indicates when private mode is enabled.

            * `{current_url}`: URL of the current web page.

            * `{protocol}`: Protocol (http/https/...) of the current web page.

            * `{audio}`: Indicator for audio/mute status.


            """

            format_pinned: Optional[str]
            """Format to use for the tab title for pinned tabs. The same placeholders like for `tabs.title.format` are defined."""

        width: Union[int, str]
        """Width (in pixels or as percentage of the window) of the tab bar if it's vertical."""

        min_width: int
        """Minimum width (in pixels) of tabs (-1 for the default minimum size behavior).

        This setting only applies when tabs are horizontal.

        This setting does not apply to pinned tabs, unless `tabs.pinned.shrink` is False.
        """

        max_width: int
        """Maximum width (in pixels) of tabs (-1 for no maximum).

        This setting only applies when tabs are horizontal.

        This setting does not apply to pinned tabs, unless `tabs.pinned.shrink` is False.

        This setting may not apply properly if max_width is smaller than the minimum size of tab contents, or smaller than tabs.min_width.
        """

        indicator: _Indicator

        @dataclass
        class _Indicator:
            width: int
            """Width (in pixels) of the progress indicator (0 to disable)."""

            padding: Mapping[str, int]
            """Padding (in pixels) for tab indicators."""

        pinned: _Pinned

        @dataclass
        class _Pinned:
            shrink: bool
            """Shrink pinned tabs down to their contents."""

            frozen: bool
            """Force pinned tabs to stay at fixed URL."""

        undo_stack_size: int
        """Number of closed tabs (per window) and closed windows to remember for :undo (-1 for no maximum)."""

        wrap: bool
        """Wrap when changing tabs."""

        focus_stack_size: int
        """Maximum stack size to remember for tab switches (-1 for no maximum)."""

        tooltips: bool
        """Show tooltips on tabs.

        Note this setting only affects windows opened after it has been set.
        """

    url: _Url

    @dataclass
    class _Url:
        auto_search: Literal["naive", "dns", "never", "schemeless"]
        """What search to start when something else than a URL is entered."""

        default_page: str
        """Page to open if :open -t/-b/-w is used without URL.

        Use `about:blank` for a blank page.
        """

        incdec_segments: list[Literal["host", "port", "path", "query", "anchor"]]
        """URL segments where `:navigate increment/decrement` will search for a number."""

        open_base_url: bool
        """Open base URL of the searchengine if a searchengine shortcut is invoked without parameters."""

        searchengines: Mapping[str, str]
        """Search engines which can be used via the address bar.



        Maps a search engine name (such as `DEFAULT`, or `ddg`) to a URL with a

        `{}` placeholder. The placeholder will be replaced by the search term, use

        `{{` and `}}` for literal `{`/`}` braces.



        The following further placeholds are defined to configure how special

        characters in the search terms are replaced by safe characters (called

        'quoting'):



        * `{}` and `{semiquoted}` quote everything except slashes; this is the most

          sensible choice for almost all search engines (for the search term

          `slash/and&amp` this placeholder expands to `slash/and%26amp`).

        * `{quoted}` quotes all characters (for `slash/and&amp` this placeholder

          expands to `slash%2Fand%26amp`).

        * `{unquoted}` quotes nothing (for `slash/and&amp` this placeholder

          expands to `slash/and&amp`).

        * `{0}` means the same as `{}`, but can be used multiple times.



        The search engine named `DEFAULT` is used when `url.auto_search` is turned

        on and something else than a URL was entered to be opened. Other search

        engines can be used by prepending the search engine name to the search

        term, e.g. `:open google qutebrowser`.


        """

        start_pages: Union[str, list[str]]
        """Page(s) to open at the start."""

        yank_ignored_parameters: Optional[list[str]]
        """URL parameters to strip when yanking a URL."""

    window: _Window

    @dataclass
    class _Window:
        hide_decoration: bool
        """Hide the window decoration.



        This setting requires a restart on Wayland.


        """

        title_format: str
        """Format to use for the window title. The same placeholders like for

        `tabs.title.format` are defined.


        """

        transparent: bool
        """Set the main window background to transparent.



        This allows having a transparent tab- or statusbar (might require a compositor such

        as picom). However, it breaks some functionality such as dmenu embedding via its

        `-w` option. On some systems, it was additionally reported that main window

        transparency negatively affects performance.



        Note this setting only affects windows opened after setting it.


        """

    zoom: _Zoom

    @dataclass
    class _Zoom:
        default: Union[float, int, str]
        """Default zoom level."""

        levels: list[Union[float, int, str]]
        """Available zoom levels."""

        mouse_divider: int
        """Number of zoom increments to divide the mouse wheel movements to."""

        text_only: bool
        """Apply the zoom factor on a frame only to the text or to all content."""

    colors: _Colors

    @dataclass
    class _Colors:
        completion: _Completion

        @dataclass
        class _Completion:
            fg: Union[str, list[str]]
            """Text color of the completion widget.

            May be a single color to use for all columns or a list of three colors, one for each column.
            """

            odd: _Odd

            @dataclass
            class _Odd:
                bg: str
                """Background color of the completion widget for odd rows."""

            even: _Even

            @dataclass
            class _Even:
                bg: str
                """Background color of the completion widget for even rows."""

            category: _Category

            @dataclass
            class _Category:
                fg: str
                """Foreground color of completion widget category headers."""

                bg: str
                """Background color of the completion widget category headers."""

                border: _Border

                @dataclass
                class _Border:
                    top: str
                    """Top border color of the completion widget category headers."""

                    bottom: str
                    """Bottom border color of the completion widget category headers."""

            item: _Item

            @dataclass
            class _Item:
                selected: _Selected

                @dataclass
                class _Selected:
                    fg: str
                    """Foreground color of the selected completion item."""

                    bg: str
                    """Background color of the selected completion item."""

                    border: _Border

                    @dataclass
                    class _Border:
                        top: str
                        """Top border color of the selected completion item."""

                        bottom: str
                        """Bottom border color of the selected completion item."""

                    match: _Match

                    @dataclass
                    class _Match:
                        fg: str
                        """Foreground color of the matched text in the selected completion item."""

            match: _Match

            @dataclass
            class _Match:
                fg: str
                """Foreground color of the matched text in the completion."""

            scrollbar: _Scrollbar

            @dataclass
            class _Scrollbar:
                fg: str
                """Color of the scrollbar handle in the completion view."""

                bg: str
                """Color of the scrollbar in the completion view."""

        tooltip: _Tooltip

        @dataclass
        class _Tooltip:
            bg: Optional[Optional[str]]
            """Background color of tooltips.

            If set to null, the Qt default is used.
            """

            fg: Optional[Optional[str]]
            """Foreground color of tooltips.

            If set to null, the Qt default is used.
            """

        contextmenu: _Contextmenu

        @dataclass
        class _Contextmenu:
            menu: _Menu

            @dataclass
            class _Menu:
                bg: Optional[Optional[str]]
                """Background color of the context menu.

                If set to null, the Qt default is used.
                """

                fg: Optional[Optional[str]]
                """Foreground color of the context menu.

                If set to null, the Qt default is used.
                """

            selected: _Selected

            @dataclass
            class _Selected:
                bg: Optional[Optional[str]]
                """Background color of the context menu's selected item.

                If set to null, the Qt default is used.
                """

                fg: Optional[Optional[str]]
                """Foreground color of the context menu's selected item.

                If set to null, the Qt default is used.
                """

            disabled: _Disabled

            @dataclass
            class _Disabled:
                bg: Optional[Optional[str]]
                """Background color of disabled items in the context menu.

                If set to null, the Qt default is used.
                """

                fg: Optional[Optional[str]]
                """Foreground color of disabled items in the context menu.

                If set to null, the Qt default is used.
                """

        downloads: _Downloads

        @dataclass
        class _Downloads:
            bar: _Bar

            @dataclass
            class _Bar:
                bg: str
                """Background color for the download bar."""

            start: _Start

            @dataclass
            class _Start:
                fg: str
                """Color gradient start for download text."""

                bg: str
                """Color gradient start for download backgrounds."""

            stop: _Stop

            @dataclass
            class _Stop:
                fg: str
                """Color gradient end for download text."""

                bg: str
                """Color gradient stop for download backgrounds."""

            system: _System

            @dataclass
            class _System:
                fg: Literal["rgb", "hsv", "hsl", "none"]
                """Color gradient interpolation system for download text."""

                bg: Literal["rgb", "hsv", "hsl", "none"]
                """Color gradient interpolation system for download backgrounds."""

            error: _Error

            @dataclass
            class _Error:
                fg: str
                """Foreground color for downloads with errors."""

                bg: str
                """Background color for downloads with errors."""

        hints: _Hints

        @dataclass
        class _Hints:
            fg: str
            """Font color for hints."""

            bg: str
            """Background color for hints.

            Note that you can use a `rgba(...)` value for transparency.
            """

            match: _Match

            @dataclass
            class _Match:
                fg: str
                """Font color for the matched part of hints."""

        keyhint: _Keyhint

        @dataclass
        class _Keyhint:
            fg: str
            """Text color for the keyhint widget."""

            suffix: _Suffix

            @dataclass
            class _Suffix:
                fg: str
                """Highlight color for keys to complete the current keychain."""

            bg: str
            """Background color of the keyhint widget."""

        messages: _Messages

        @dataclass
        class _Messages:
            error: _Error

            @dataclass
            class _Error:
                fg: str
                """Foreground color of an error message."""

                bg: str
                """Background color of an error message."""

                border: str
                """Border color of an error message."""

            warning: _Warning

            @dataclass
            class _Warning:
                fg: str
                """Foreground color of a warning message."""

                bg: str
                """Background color of a warning message."""

                border: str
                """Border color of a warning message."""

            info: _Info

            @dataclass
            class _Info:
                fg: str
                """Foreground color of an info message."""

                bg: str
                """Background color of an info message."""

                border: str
                """Border color of an info message."""

        prompts: _Prompts

        @dataclass
        class _Prompts:
            fg: str
            """Foreground color for prompts."""

            border: str
            """Border used around UI elements in prompts."""

            bg: str
            """Background color for prompts."""

            selected: _Selected

            @dataclass
            class _Selected:
                fg: str
                """Foreground color for the selected item in filename prompts."""

                bg: str
                """Background color for the selected item in filename prompts."""

        statusbar: _Statusbar

        @dataclass
        class _Statusbar:
            normal: _Normal

            @dataclass
            class _Normal:
                fg: str
                """Foreground color of the statusbar."""

                bg: str
                """Background color of the statusbar."""

            insert: _Insert

            @dataclass
            class _Insert:
                fg: str
                """Foreground color of the statusbar in insert mode."""

                bg: str
                """Background color of the statusbar in insert mode."""

            passthrough: _Passthrough

            @dataclass
            class _Passthrough:
                fg: str
                """Foreground color of the statusbar in passthrough mode."""

                bg: str
                """Background color of the statusbar in passthrough mode."""

            private: _Private

            @dataclass
            class _Private:
                fg: str
                """Foreground color of the statusbar in private browsing mode."""

                bg: str
                """Background color of the statusbar in private browsing mode."""

            command: _Command

            @dataclass
            class _Command:
                fg: str
                """Foreground color of the statusbar in command mode."""

                bg: str
                """Background color of the statusbar in command mode."""

                private: _Private

                @dataclass
                class _Private:
                    fg: str
                    """Foreground color of the statusbar in private browsing + command mode."""

                    bg: str
                    """Background color of the statusbar in private browsing + command mode."""

            caret: _Caret

            @dataclass
            class _Caret:
                fg: str
                """Foreground color of the statusbar in caret mode."""

                bg: str
                """Background color of the statusbar in caret mode."""

                selection: _Selection

                @dataclass
                class _Selection:
                    fg: str
                    """Foreground color of the statusbar in caret mode with a selection."""

                    bg: str
                    """Background color of the statusbar in caret mode with a selection."""

            progress: _Progress

            @dataclass
            class _Progress:
                bg: str
                """Background color of the progress bar."""

            url: _Url

            @dataclass
            class _Url:
                fg: str
                """Default foreground color of the URL in the statusbar."""

                error: _Error

                @dataclass
                class _Error:
                    fg: str
                    """Foreground color of the URL in the statusbar on error."""

                hover: _Hover

                @dataclass
                class _Hover:
                    fg: str
                    """Foreground color of the URL in the statusbar for hovered links."""

                success: _Success

                @dataclass
                class _Success:
                    http: _Http

                    @dataclass
                    class _Http:
                        fg: str
                        """Foreground color of the URL in the statusbar on successful load (http)."""

                    https: _Https

                    @dataclass
                    class _Https:
                        fg: str
                        """Foreground color of the URL in the statusbar on successful load (https)."""

                warn: _Warn

                @dataclass
                class _Warn:
                    fg: str
                    """Foreground color of the URL in the statusbar when there's a warning."""

        tabs: _Tabs

        @dataclass
        class _Tabs:
            bar: _Bar

            @dataclass
            class _Bar:
                bg: str
                """Background color of the tab bar."""

            indicator: _Indicator

            @dataclass
            class _Indicator:
                start: str
                """Color gradient start for the tab indicator."""

                stop: str
                """Color gradient end for the tab indicator."""

                error: str
                """Color for the tab indicator on errors."""

                system: Literal["rgb", "hsv", "hsl", "none"]
                """Color gradient interpolation system for the tab indicator."""

            odd: _Odd

            @dataclass
            class _Odd:
                fg: str
                """Foreground color of unselected odd tabs."""

                bg: str
                """Background color of unselected odd tabs."""

            even: _Even

            @dataclass
            class _Even:
                fg: str
                """Foreground color of unselected even tabs."""

                bg: str
                """Background color of unselected even tabs."""

            selected: _Selected

            @dataclass
            class _Selected:
                odd: _Odd

                @dataclass
                class _Odd:
                    fg: str
                    """Foreground color of selected odd tabs."""

                    bg: str
                    """Background color of selected odd tabs."""

                even: _Even

                @dataclass
                class _Even:
                    fg: str
                    """Foreground color of selected even tabs."""

                    bg: str
                    """Background color of selected even tabs."""

            pinned: _Pinned

            @dataclass
            class _Pinned:
                odd: _Odd

                @dataclass
                class _Odd:
                    fg: str
                    """Foreground color of pinned unselected odd tabs."""

                    bg: str
                    """Background color of pinned unselected odd tabs."""

                even: _Even

                @dataclass
                class _Even:
                    fg: str
                    """Foreground color of pinned unselected even tabs."""

                    bg: str
                    """Background color of pinned unselected even tabs."""

                selected: _Selected

                @dataclass
                class _Selected:
                    odd: _Odd

                    @dataclass
                    class _Odd:
                        fg: str
                        """Foreground color of pinned selected odd tabs."""

                        bg: str
                        """Background color of pinned selected odd tabs."""

                    even: _Even

                    @dataclass
                    class _Even:
                        fg: str
                        """Foreground color of pinned selected even tabs."""

                        bg: str
                        """Background color of pinned selected even tabs."""

        webpage: _Webpage

        @dataclass
        class _Webpage:
            bg: Optional[str]
            """Background color for webpages if unset (or empty to use the theme's color)."""

            preferred_color_scheme: Literal["auto", "light", "dark"]
            """Value to use for `prefers-color-scheme:` for websites.

            The "light" value is only available with QtWebEngine 5.15.2+. On older versions, it is the same as "auto".

            The "auto" value is broken on QtWebEngine 5.15.2 due to a Qt bug. There, it will fall back to "light" unconditionally.
            """

            darkmode: _Darkmode

            @dataclass
            class _Darkmode:
                enabled: bool
                """Render all web contents using a dark theme.

                On QtWebEngine < 6.7, this setting requires a restart and does not support URL patterns, only the global setting is applied.

                Example configurations from Chromium's `chrome://flags`:

                - "With simple HSL/CIELAB/RGB-based inversion": Set

                  `colors.webpage.darkmode.algorithm` accordingly, and

                  set `colors.webpage.darkmode.policy.images` to `never`.



                - "With selective image inversion": qutebrowser default settings.
                """

                algorithm: Literal[
                    "lightness-cielab", "lightness-hsl", "brightness-rgb"
                ]
                """Which algorithm to use for modifying how colors are rendered with dark mode.

                The `lightness-cielab` value was added with QtWebEngine 5.14 and is treated like `lightness-hsl` with older QtWebEngine versions.
                """

                contrast: float
                """Contrast for dark mode.

                This only has an effect when `colors.webpage.darkmode.algorithm` is set to `lightness-hsl` or `brightness-rgb`.
                """

                policy: _Policy

                @dataclass
                class _Policy:
                    images: Literal["always", "never", "smart", "smart-simple"]
                    """Which images to apply dark mode to."""

                    page: Literal["always", "smart"]
                    """Which pages to apply dark mode to.

                    The underlying Chromium setting has been removed in QtWebEngine 5.15.3, thus this setting is ignored there. Instead, every element is now classified individually.
                    """

                threshold: _Threshold

                @dataclass
                class _Threshold:
                    foreground: int
                    """Threshold for inverting text with dark mode.

                    Text colors with brightness below this threshold will be inverted, and above it will be left as in the original, non-dark-mode page. Set to 256 to always invert text color or to 0 to never invert text color.
                    """

                    background: int
                    """Threshold for inverting background elements with dark mode.

                    Background elements with brightness above this threshold will be inverted, and below it will be left as in the original, non-dark-mode page. Set to 256 to never invert the color or to 0 to always invert it.

                    Note: This behavior is the opposite of `colors.webpage.darkmode.threshold.foreground`!
                    """

    fonts: _Fonts

    @dataclass
    class _Fonts:
        default_family: Optional[Union[str, Optional[list[str]]]]
        """Default font families to use.

        Whenever "default_family" is used in a font setting, it's replaced with the fonts listed here.

        If set to an empty value, a system-specific monospace default is used.
        """

        default_size: str
        """Default font size to use.

        Whenever "default_size" is used in a font setting, it's replaced with the size listed here.

        Valid values are either a float value with a "pt" suffix, or an integer value with a "px" suffix.
        """

        completion: _Completion

        @dataclass
        class _Completion:
            entry: str
            """Font used in the completion widget."""

            category: str
            """Font used in the completion categories."""

        tooltip: Optional[Optional[str]]
        """Font used for tooltips.

        If set to null, the Qt default is used.
        """

        contextmenu: Optional[Optional[str]]
        """Font used for the context menu.

        If set to null, the Qt default is used.
        """

        debug_console: str
        """Font used for the debugging console."""

        downloads: str
        """Font used for the downloadbar."""

        hints: str
        """Font used for the hints."""

        keyhint: str
        """Font used in the keyhint widget."""

        messages: _Messages

        @dataclass
        class _Messages:
            error: str
            """Font used for error messages."""

            info: str
            """Font used for info messages."""

            warning: str
            """Font used for warning messages."""

        prompts: str
        """Font used for prompts."""

        statusbar: str
        """Font used in the statusbar."""

        tabs: _Tabs

        @dataclass
        class _Tabs:
            selected: str
            """Font used for selected tabs."""

            unselected: str
            """Font used for unselected tabs."""

        web: _Web

        @dataclass
        class _Web:
            family: _Family

            @dataclass
            class _Family:
                standard: Optional[str]
                """Font family for standard fonts."""

                fixed: Optional[str]
                """Font family for fixed fonts."""

                serif: Optional[str]
                """Font family for serif fonts."""

                sans_serif: Optional[str]
                """Font family for sans-serif fonts."""

                cursive: Optional[str]
                """Font family for cursive fonts."""

                fantasy: Optional[str]
                """Font family for fantasy fonts."""

            size: _Size

            @dataclass
            class _Size:
                default: int
                """Default font size (in pixels) for regular text."""

                default_fixed: int
                """Default font size (in pixels) for fixed-pitch text."""

                minimum: int
                """Hard minimum font size (in pixels)."""

                minimum_logical: int
                """Minimum logical font size (in pixels) that is applied when zooming out."""

    bindings: _Bindings

    @dataclass
    class _Bindings:
        key_mappings: Optional[Mapping[str, str]]
        """Map keys to other keys, so that they are equivalent in all modes.

        When the key used as dictionary-key is pressed, the binding for the key used as dictionary-value is invoked instead.

        This is useful for global remappings of keys, for example to map <Ctrl-[> to <Escape>.

        NOTE: This should only be used if two keys should always be equivalent, i.e. for things like <Enter> (keypad) and <Return> (non-keypad). For normal command bindings, qutebrowser works differently to vim: You always bind keys to commands, usually via `:bind` or `config.bind()`. Instead of using this setting, consider finding the command a key is bound to (e.g. via `:bind gg`) and then binding the same command to the desired key.

        Note that when a key is bound (via `bindings.default` or `bindings.commands`), the mapping is ignored.
        """

        default: Optional[Mapping[str, Optional[Mapping[str, str]]]]
        """Default keybindings. If you want to add bindings, modify `bindings.commands` instead.

        The main purpose of this setting is that you can set it to an empty dictionary if you want to load no default keybindings at all.

        If you want to preserve default bindings (and get new bindings when there is an update), use `config.bind()` in `config.py` or the `:bind` command, and leave this setting alone.
        """

        commands: Optional[Mapping[str, Optional[Mapping[str, Optional[str]]]]]
        """Keybindings mapping keys to commands in different modes.

        While it's possible to add bindings with this setting, it's recommended to use `config.bind()` in `config.py` or the `:bind` command, and leave this setting alone.

        This setting is a dictionary containing mode names and dictionaries mapping keys to commands:

        `{mode: {key: command}}`

        If you want to map a key to another key, check the `bindings.key_mappings` setting instead.

        For modifiers, you can use either `-` or `+` as delimiters, and these names:



          * Control: `Control`, `Ctrl`



          * Meta:    `Meta`, `Windows`, `Mod4`



          * Alt:     `Alt`, `Mod1`



          * Shift:   `Shift`



        For simple keys (no `<>`-signs), a capital letter means the key is pressed with Shift. For special keys (with `<>`-signs), you need to explicitly add `Shift-` to match a key pressed with shift.

        If you want a binding to do nothing, bind it to the `nop` command. If you want a default binding to be passed through to the website, bind it to null.

        Note that some commands which are only useful for bindings (but not used interactively) are hidden from the command completion. See `:help` for a full list of available commands.

        The following modes are available:



        * normal: Default mode, where most commands are invoked.



        * insert: Entered when an input field is focused on a website, or by

          pressing `i` in normal mode. Passes through almost all keypresses to the

          website, but has some bindings like `<Ctrl-e>` to open an external

          editor. Note that single keys can't be bound in this mode.



        * hint: Entered when `f` is pressed to select links with the keyboard. Note

          that single keys can't be bound in this mode.



        * passthrough: Similar to insert mode, but passes through all keypresses

          except `<Shift+Escape>` to leave the mode. Note that single keys can't be

          bound in this mode.



        * command: Entered when pressing the `:` key in order to enter a command.

          Note that single keys can't be bound in this mode.



        * prompt: Entered when there's a prompt to display, like for download

          locations or when invoked from JavaScript.



        * yesno: Entered when there's a yes/no prompt displayed.

        * caret: Entered when pressing the `v` mode, used to select text using the

          keyboard.



        * register: Entered when qutebrowser is waiting for a register name/key for

          commands like `:set-mark`.
        """

    logging: _Logging

    @dataclass
    class _Logging:
        level: _Level

        @dataclass
        class _Level:
            ram: Literal["vdebug", "debug", "info", "warning", "error", "critical"]
            """Level for in-memory logs."""

            console: Literal["vdebug", "debug", "info", "warning", "error", "critical"]
            """Level for console (stdout/stderr) logs. Ignored if the `--loglevel` or `--debug` CLI flags are used."""
