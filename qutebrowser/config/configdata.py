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

"""Configuration data for config.py.

Module attributes:

FIRST_COMMENT: The initial comment header to place in the config.
SECTION_DESC: A dictionary with descriptions for sections.
DATA: A global read-only copy of the default config, an OrderedDict of
      sections.
"""

import sys
import re
import collections

from qutebrowser.config import configtypes as typ
from qutebrowser.config import sections as sect
from qutebrowser.config.value import SettingValue
from qutebrowser.utils.qtutils import MAXVALS


FIRST_COMMENT = r"""
# vim: ft=dosini

# Configfile for qutebrowser.
#
# This configfile is parsed by python's configparser in extended
# interpolation mode. The format is very INI-like, so there are
# categories like [general] with "key = value"-pairs.
#
# Note that you shouldn't add your own comments, as this file is
# regenerated every time the config is saved.
#
# Interpolation looks like  ${value}  or  ${section:value} and will be
# replaced by the respective value.
#
# Some settings will expand environment variables. Note that, since
# interpolation is run first, you will need to escape the  $  char as
# described below.
#
# This is the default config, so if you want to remove anything from
# here (as opposed to change/add), for example a key binding, set it to
# an empty value.
#
# You will need to escape the following values:
#   - # at the start of the line (at the first position of the key) (\#)
#   - $ in a value ($$)
"""


SECTION_DESC = {
    'general': "General/miscellaneous options.",
    'ui': "General options related to the user interface.",
    'input': "Options related to input modes.",
    'network': "Settings related to the network.",
    'completion': "Options related to completion and command history.",
    'tabs': "Configuration of the tab bar.",
    'storage': "Settings related to cache and storage.",
    'content': "Loaded plugins/scripts and allowed actions.",
    'hints': "Hinting settings.",
    'searchengines': (
        "Definitions of search engines which can be used via the address "
        "bar.\n"
        "The searchengine named `DEFAULT` is used when "
        "`general -> auto-search` is true and something else than a URL was "
        "entered to be opened. Other search engines can be used by prepending "
        "the search engine name to the search term, e.g. "
        "`:open google qutebrowser`. The string `{}` will be replaced by the "
        "search term, use `{{` and `}}` for literal `{`/`}` signs."),
    'aliases': (
        "Aliases for commands.\n"
        "By default, no aliases are defined. Example which adds a new command "
        "`:qtb` to open qutebrowsers website:\n\n"
        "`qtb = open http://www.qutebrowser.org/`"),
    'colors': (
        "Colors used in the UI.\n"
        "A value can be in one of the following format:\n\n"
        " * `#RGB`/`#RRGGBB`/`#RRRGGGBBB`/`#RRRRGGGGBBBB`\n"
        " * A SVG color name as specified in http://www.w3.org/TR/SVG/"
        "types.html#ColorKeywords[the W3C specification].\n"
        " * transparent (no color)\n"
        " * `rgb(r, g, b)` / `rgba(r, g, b, a)` (values 0-255 or "
        "percentages)\n"
        " * `hsv(h, s, v)` / `hsva(h, s, v, a)` (values 0-255, hue 0-359)\n"
        " * A gradient as explained in http://doc.qt.io/qt-5/"
        "stylesheet-reference.html#list-of-property-types[the Qt "
        "documentation] under ``Gradient''.\n\n"
        "A *.system value determines the color system to use for color "
        "interpolation between similarly-named *.start and *.stop entries, "
        "regardless of how they are defined in the options. "
        "Valid values are 'rgb', 'hsv', and 'hsl'.\n\n"
        "The `hints.*` values are a special case as they're real CSS "
        "colors, not Qt-CSS colors. There, for a gradient, you need to use "
        "`-webkit-gradient`, see https://www.webkit.org/blog/175/introducing-"
        "css-gradients/[the WebKit documentation]."),
    'fonts': (
        "Fonts used for the UI, with optional style/weight/size.\n\n"
        " * Style: `normal`/`italic`/`oblique`\n"
        " * Weight: `normal`, `bold`, `100`..`900`\n"
        " * Size: _number_ `px`/`pt`"),
}


DEFAULT_FONT_SIZE = '10pt' if sys.platform == 'darwin' else '8pt'


def data(readonly=False):
    """Get the default config data.

    Return:
        A {name: section} OrderedDict.
    """
    return collections.OrderedDict([
        ('general', sect.KeyValue(
            ('ignore-case',
             SettingValue(typ.IgnoreCase(), 'smart'),
             "Whether to find text on a page case-insensitively."),

            ('wrap-search',
             SettingValue(typ.Bool(), 'true'),
             "Whether to wrap finding text to the top when arriving at the "
             "end."),

            ('startpage',
             SettingValue(typ.List(), 'https://www.duckduckgo.com'),
             "The default page(s) to open at the start, separated by commas."),

            ('default-page',
             SettingValue(typ.FuzzyUrl(), '${startpage}'),
             "The page to open if :open -t/-b/-w is used without URL. Use "
             "`about:blank` for a blank page."),

            ('auto-search',
             SettingValue(typ.AutoSearch(), 'naive'),
             "Whether to start a search when something else than a URL is "
             "entered."),

            ('auto-save-config',
             SettingValue(typ.Bool(), 'true'),
             "Whether to save the config automatically on quit."),

            ('auto-save-interval',
             SettingValue(typ.Int(minval=0), '15000'),
             "How often (in milliseconds) to auto-save config/cookies/etc."),

            ('editor',
             SettingValue(typ.ShellCommand(placeholder=True), 'gvim -f "{}"'),
             "The editor (and arguments) to use for the `open-editor` "
             "command.\n\n"
             "Use `{}` for the filename. The value gets split like in a "
             "shell, so you can use `\"` or `'` to quote arguments."),

            ('editor-encoding',
             SettingValue(typ.Encoding(), 'utf-8'),
             "Encoding to use for editor."),

            ('private-browsing',
             SettingValue(typ.Bool(), 'false'),
             "Do not record visited pages in the history or store web page "
             "icons."),

            ('developer-extras',
             SettingValue(typ.Bool(), 'false'),
             "Enable extra tools for Web developers.\n\n"
             "This needs to be enabled for `:inspector` to work and also adds "
             "an _Inspect_ entry to the context menu."),

            ('print-element-backgrounds',
             SettingValue(typ.Bool(), 'true'),
             "Whether the background color and images are also drawn when the "
             "page is printed."),

            ('xss-auditing',
             SettingValue(typ.Bool(), 'false'),
             "Whether load requests should be monitored for cross-site "
             "scripting attempts.\n\n"
             "Suspicious scripts will be blocked and reported in the "
             "inspector's JavaScript console. Enabling this feature might "
             "have an impact on performance."),

            ('site-specific-quirks',
             SettingValue(typ.Bool(), 'true'),
             "Enable workarounds for broken sites."),

            ('default-encoding',
             SettingValue(typ.String(none_ok=True), ''),
             "Default encoding to use for websites.\n\n"
             "The encoding must be a string describing an encoding such as "
             "_utf-8_, _iso-8859-1_, etc. If left empty a default value will "
             "be used."),

            ('new-instance-open-target',
             SettingValue(typ.NewInstanceOpenTarget(), 'tab'),
             "How to open links in an existing instance if a new one is "
             "launched."),

            ('log-javascript-console',
             SettingValue(typ.Bool(), 'false'),
             "Whether to log javascript console messages."),

            ('save-session',
             SettingValue(typ.Bool(), 'false'),
             "Whether to always save the open pages."),

            ('session-default-name',
             SettingValue(typ.SessionName(none_ok=True), ''),
             "The name of the session to save by default, or empty for the "
             "last loaded session."),

            readonly=readonly
        )),

        ('ui', sect.KeyValue(
            ('zoom-levels',
             SettingValue(typ.PercList(minval=0),
                          '25%,33%,50%,67%,75%,90%,100%,110%,125%,150%,175%,'
                          '200%,250%,300%,400%,500%'),
             "The available zoom levels, separated by commas."),

            ('default-zoom',
             SettingValue(typ.Perc(), '100%'),
             "The default zoom level."),

            ('downloads-position',
             SettingValue(typ.VerticalPosition(), 'top'),
             "Where to show the downloaded files."),

            ('message-timeout',
             SettingValue(typ.Int(), '2000'),
             "Time (in ms) to show messages in the statusbar for."),

            ('message-unfocused',
             SettingValue(typ.Bool(), 'false'),
             "Whether to show messages in unfocused windows."),

            ('confirm-quit',
             SettingValue(typ.ConfirmQuit(), 'never'),
             "Whether to confirm quitting the application."),

            ('display-statusbar-messages',
             SettingValue(typ.Bool(), 'false'),
             "Whether to display javascript statusbar messages."),

            ('zoom-text-only',
             SettingValue(typ.Bool(), 'false'),
             "Whether the zoom factor on a frame applies only to the text or "
             "to all content."),

            ('frame-flattening',
             SettingValue(typ.Bool(), 'false'),
             "Whether to  expand each subframe to its contents.\n\n"
             "This will flatten all the frames to become one scrollable "
             "page."),

            ('user-stylesheet',
             SettingValue(typ.UserStyleSheet(none_ok=True),
                          '::-webkit-scrollbar { width: 0px; height: 0px; }'),
             "User stylesheet to use (absolute filename, filename relative to "
             "the config directory or CSS string). Will expand environment "
             "variables."),

            ('css-media-type',
             SettingValue(typ.String(none_ok=True), ''),
             "Set the CSS media type."),

            ('smooth-scrolling',
             SettingValue(typ.Bool(), 'false'),
             "Whether to enable smooth scrolling for webpages."),

            ('remove-finished-downloads',
             SettingValue(typ.Bool(), 'false'),
             "Whether to remove finished downloads automatically."),

            ('hide-statusbar',
             SettingValue(typ.Bool(), 'false'),
             "Whether to hide the statusbar unless a message is shown."),

            ('statusbar-padding',
             SettingValue(typ.Padding(), '1,1,0,0'),
             "Padding for statusbar (top, bottom, left, right)."),

            ('window-title-format',
             SettingValue(typ.FormatString(fields=['perc', 'perc_raw', 'title',
                                                   'title_sep', 'id']),
                          '{perc}{title}{title_sep}qutebrowser'),
             "The format to use for the window title. The following "
             "placeholders are defined:\n\n"
             "* `{perc}`: The percentage as a string like `[10%]`.\n"
             "* `{perc_raw}`: The raw percentage, e.g. `10`\n"
             "* `{title}`: The title of the current web page\n"
             "* `{title_sep}`: The string ` - ` if a title is set, empty "
             "otherwise.\n"
             "* `{id}`: The internal window ID of this window."),

            ('hide-mouse-cursor',
             SettingValue(typ.Bool(), 'false'),
             "Whether to hide the mouse cursor."),

            ('modal-js-dialog',
             SettingValue(typ.Bool(), 'false'),
             "Use standard JavaScript modal dialog for alert() and confirm()"),

            readonly=readonly
        )),

        ('network', sect.KeyValue(
            ('do-not-track',
             SettingValue(typ.Bool(), 'true'),
             "Value to send in the `DNT` header."),

            ('accept-language',
             SettingValue(typ.String(none_ok=True), 'en-US,en'),
             "Value to send in the `accept-language` header."),

            ('referer-header',
             SettingValue(typ.Referer(), 'same-domain'),
             "Send the Referer header"),

            ('user-agent',
             SettingValue(typ.UserAgent(none_ok=True), ''),
             "User agent to send. Empty to send the default."),

            ('proxy',
             SettingValue(typ.Proxy(), 'system'),
             "The proxy to use.\n\n"
             "In addition to the listed values, you can use a `socks://...` "
             "or `http://...` URL."),

            ('proxy-dns-requests',
             SettingValue(typ.Bool(), 'true'),
             "Whether to send DNS requests over the configured proxy."),

            ('ssl-strict',
             SettingValue(typ.BoolAsk(), 'ask'),
             "Whether to validate SSL handshakes."),

            ('dns-prefetch',
             SettingValue(typ.Bool(), 'true'),
             "Whether to try to pre-fetch DNS entries to speed up browsing."),

            readonly=readonly
        )),

        ('completion', sect.KeyValue(
            ('auto-open',
             SettingValue(typ.Bool(), 'true'),
             "Automatically open completion when typing."),

            ('download-path-suggestion',
             SettingValue(typ.DownloadPathSuggestion(), 'path'),
             "What to display in the download filename input."),

            ('timestamp-format',
             SettingValue(typ.String(none_ok=True), '%Y-%m-%d'),
             "How to format timestamps (e.g. for history)"),

            ('show',
             SettingValue(typ.Bool(), 'true'),
             "Whether to show the autocompletion window."),

            ('height',
             SettingValue(typ.PercOrInt(minperc=0, maxperc=100, minint=1),
                          '50%'),
             "The height of the completion, in px or as percentage of the "
             "window."),

            ('cmd-history-max-items',
             SettingValue(typ.Int(minval=-1), '100'),
             "How many commands to save in the command history.\n\n"
             "0: no history / -1: unlimited"),

            ('web-history-max-items',
             SettingValue(typ.Int(minval=-1), '1000'),
             "How many URLs to show in the web history.\n\n"
             "0: no history / -1: unlimited"),

            ('quick-complete',
             SettingValue(typ.Bool(), 'true'),
             "Whether to move on to the next part when there's only one "
             "possible completion left."),

            ('shrink',
             SettingValue(typ.Bool(), 'false'),
             "Whether to shrink the completion to be smaller than the "
             "configured size if there are no scrollbars."),

            readonly=readonly
        )),

        ('input', sect.KeyValue(
            ('timeout',
             SettingValue(typ.Int(minval=0, maxval=MAXVALS['int']), '500'),
             "Timeout for ambiguous key bindings."),

            ('partial-timeout',
             SettingValue(typ.Int(minval=0, maxval=MAXVALS['int']), '1000'),
             "Timeout for partially typed key bindings."),

            ('insert-mode-on-plugins',
             SettingValue(typ.Bool(), 'false'),
             "Whether to switch to insert mode when clicking flash and other "
             "plugins."),

            ('auto-leave-insert-mode',
             SettingValue(typ.Bool(), 'true'),
             "Whether to leave insert mode if a non-editable element is "
             "clicked."),

            ('auto-insert-mode',
             SettingValue(typ.Bool(), 'false'),
             "Whether to automatically enter insert mode if an editable "
             "element is focused after page load."),

            ('forward-unbound-keys',
             SettingValue(typ.ForwardUnboundKeys(), 'auto'),
             "Whether to forward unbound keys to the webview in normal mode."),

            ('spatial-navigation',
             SettingValue(typ.Bool(), 'false'),
             "Enables or disables the Spatial Navigation feature.\n\n"
             "Spatial navigation consists in the ability to navigate between "
             "focusable elements in a Web page, such as hyperlinks and form "
             "controls, by using Left, Right, Up and Down arrow keys. For "
             "example, if a user presses the Right key, heuristics determine "
             "whether there is an element he might be trying to reach towards "
             "the right and which element he probably wants."),

            ('links-included-in-focus-chain',
             SettingValue(typ.Bool(), 'true'),
             "Whether hyperlinks should be included in the keyboard focus "
             "chain."),

            ('rocker-gestures',
             SettingValue(typ.Bool(), 'false'),
             "Whether to enable Opera-like mouse rocker gestures. This "
             "disables the context menu."),

            ('mouse-zoom-divider',
             SettingValue(typ.Int(minval=1), '512'),
             "How much to divide the mouse wheel movements to translate them "
             "into zoom increments."),

            readonly=readonly
        )),

        ('tabs', sect.KeyValue(
            ('background-tabs',
             SettingValue(typ.Bool(), 'false'),
             "Whether to open new tabs (middleclick/ctrl+click) in "
             "background."),

            ('select-on-remove',
             SettingValue(typ.SelectOnRemove(), 'right'),
             "Which tab to select when the focused tab is removed."),

            ('new-tab-position',
             SettingValue(typ.NewTabPosition(), 'right'),
             "How new tabs are positioned."),

            ('new-tab-position-explicit',
             SettingValue(typ.NewTabPosition(), 'last'),
             "How new tabs opened explicitly are positioned."),

            ('last-close',
             SettingValue(typ.LastClose(), 'ignore'),
             "Behavior when the last tab is closed."),

            ('show',
             SettingValue(typ.TabBarShow(), 'always'),
             "When to show the tab bar"),

            ('show-switching-delay',
             SettingValue(typ.Int(), '800'),
             "Time to show the tab bar before hiding it when tabs->show is "
             "set to 'switching'."),

            ('wrap',
             SettingValue(typ.Bool(), 'true'),
             "Whether to wrap when changing tabs."),

            ('movable',
             SettingValue(typ.Bool(), 'true'),
             "Whether tabs should be movable."),

            ('close-mouse-button',
             SettingValue(typ.CloseButton(), 'middle'),
             "On which mouse button to close tabs."),

            ('position',
             SettingValue(typ.Position(), 'top'),
             "The position of the tab bar."),

            ('show-favicons',
             SettingValue(typ.Bool(), 'true'),
             "Whether to show favicons in the tab bar."),

            ('width',
             SettingValue(typ.PercOrInt(minperc=0, maxperc=100, minint=1),
                          '20%'),
             "The width of the tab bar if it's vertical, in px or as "
             "percentage of the window."),

            ('indicator-width',
             SettingValue(typ.Int(minval=0), '3'),
             "Width of the progress indicator (0 to disable)."),

            ('tabs-are-windows',
             SettingValue(typ.Bool(), 'false'),
             "Whether to open windows instead of tabs."),

            ('title-format',
             SettingValue(typ.FormatString(
                 fields=['perc', 'perc_raw', 'title', 'title_sep', 'index',
                         'id']), '{index}: {title}'),
             "The format to use for the tab title. The following placeholders "
             "are defined:\n\n"
             "* `{perc}`: The percentage as a string like `[10%]`.\n"
             "* `{perc_raw}`: The raw percentage, e.g. `10`\n"
             "* `{title}`: The title of the current web page\n"
             "* `{title_sep}`: The string ` - ` if a title is set, empty "
             "otherwise.\n"
             "* `{index}`: The index of this tab.\n"
             "* `{id}`: The internal tab ID of this tab."),

            ('mousewheel-tab-switching',
             SettingValue(typ.Bool(), 'true'),
             "Switch between tabs using the mouse wheel."),

            ('padding',
             SettingValue(typ.Padding(), '0,0,5,5'),
             "Padding for tabs (top, bottom, left, right)."),

            ('indicator-padding',
             SettingValue(typ.Padding(), '2,2,0,4'),
             "Padding for indicators (top, bottom, left, right)."),

            readonly=readonly
        )),

        ('storage', sect.KeyValue(
            ('download-directory',
             SettingValue(typ.Directory(none_ok=True), ''),
             "The directory to save downloads to. An empty value selects a "
             "sensible os-specific default. Will expand environment "
             "variables."),

            ('prompt-download-directory',
             SettingValue(typ.Bool(), 'true'),
             "Whether to prompt the user for the download location.\n"
             "If set to false, 'download-directory' will be used."),

            ('remember-download-directory',
             SettingValue(typ.Bool(), 'true'),
             "Whether to remember the last used download directory."),

            ('maximum-pages-in-cache',
             SettingValue(
                 typ.Int(none_ok=True, minval=0, maxval=MAXVALS['int']), ''),
             "The maximum number of pages to hold in the global memory page "
             "cache.\n\n"
             "The Page Cache allows for a nicer user experience when "
             "navigating forth or back to pages in the forward/back history, "
             "by pausing and resuming up to _n_ pages.\n\n"
             "For more information about the feature, please refer to: "
             "http://webkit.org/blog/427/webkit-page-cache-i-the-basics/"),

            ('object-cache-capacities',
             SettingValue(
                 typ.WebKitBytesList(length=3, maxsize=MAXVALS['int'],
                                     none_ok=True), ''),
             "The capacities for the global memory cache for dead objects "
             "such as stylesheets or scripts. Syntax: cacheMinDeadCapacity, "
             "cacheMaxDead, totalCapacity.\n\n"
             "The _cacheMinDeadCapacity_ specifies the minimum number of "
             "bytes that dead objects should consume when the cache is under "
             "pressure.\n\n"
             "_cacheMaxDead_ is the maximum number of bytes that dead objects "
             "should consume when the cache is *not* under pressure.\n\n"
             "_totalCapacity_ specifies the maximum number of bytes "
             "that the cache should consume *overall*."),

            ('offline-storage-default-quota',
             SettingValue(typ.WebKitBytes(maxsize=MAXVALS['int64'],
                                          none_ok=True), ''),
             "Default quota for new offline storage databases."),

            ('offline-web-application-cache-quota',
             SettingValue(typ.WebKitBytes(maxsize=MAXVALS['int64'],
                                          none_ok=True), ''),
             "Quota for the offline web application cache."),

            ('offline-storage-database',
             SettingValue(typ.Bool(), 'true'),
             "Whether support for the HTML 5 offline storage feature is "
             "enabled."),

            ('offline-web-application-storage',
             SettingValue(typ.Bool(), 'true'),
             "Whether support for the HTML 5 web application cache feature is "
             "enabled.\n\n"
             "An application cache acts like an HTTP cache in some sense. For "
             "documents that use the application cache via JavaScript, the "
             "loader engine will first ask the application cache for the "
             "contents, before hitting the network.\n\n"
             "The feature is described in details at: "
             "http://dev.w3.org/html5/spec/Overview.html#appcache"),

            ('local-storage',
             SettingValue(typ.Bool(), 'true'),
             "Whether support for the HTML 5 local storage feature is "
             "enabled."),

            ('cache-size',
             SettingValue(typ.Int(minval=0, maxval=MAXVALS['int64']),
                          '52428800'),
             "Size of the HTTP network cache."),

            readonly=readonly
        )),

        ('content', sect.KeyValue(
            ('allow-images',
             SettingValue(typ.Bool(), 'true'),
             "Whether images are automatically loaded in web pages."),

            ('allow-javascript',
             SettingValue(typ.Bool(), 'true'),
             "Enables or disables the running of JavaScript programs."),

            ('allow-plugins',
             SettingValue(typ.Bool(), 'false'),
             "Enables or disables plugins in Web pages.\n\n"
             'Qt plugins with a mimetype such as "application/x-qt-plugin" '
             "are not affected by this setting."),

            ('webgl',
             SettingValue(typ.Bool(), 'true'),
             "Enables or disables WebGL."),

            ('css-regions',
             SettingValue(typ.Bool(), 'true'),
             "Enable or disable support for CSS regions."),

            ('hyperlink-auditing',
             SettingValue(typ.Bool(), 'false'),
             "Enable or disable hyperlink auditing (<a ping>)."),

            ('geolocation',
             SettingValue(typ.BoolAsk(), 'ask'),
             "Allow websites to request geolocations."),

            ('notifications',
             SettingValue(typ.BoolAsk(), 'ask'),
             "Allow websites to show notifications."),

            #('allow-java',
            # SettingValue(typ.Bool(), 'true'),
            # "Enables or disables Java applets. Currently Java applets are "
            # "not supported"),

            ('javascript-can-open-windows',
             SettingValue(typ.Bool(), 'false'),
             "Whether JavaScript programs can open new windows."),

            ('javascript-can-close-windows',
             SettingValue(typ.Bool(), 'false'),
             "Whether JavaScript programs can close windows."),

            ('javascript-can-access-clipboard',
             SettingValue(typ.Bool(), 'false'),
             "Whether JavaScript programs can read or write to the "
             "clipboard."),

            ('ignore-javascript-prompt',
             SettingValue(typ.Bool(), 'false'),
             "Whether all javascript prompts should be ignored."),

            ('ignore-javascript-alert',
             SettingValue(typ.Bool(), 'false'),
             "Whether all javascript alerts should be ignored."),

            ('local-content-can-access-remote-urls',
             SettingValue(typ.Bool(), 'false'),
             "Whether locally loaded documents are allowed to access remote "
             "urls."),

            ('local-content-can-access-file-urls',
             SettingValue(typ.Bool(), 'true'),
             "Whether locally loaded documents are allowed to access other "
             "local urls."),

            ('cookies-accept',
             SettingValue(typ.AcceptCookies(), 'no-3rdparty'),
             "Control which cookies to accept."),

            ('cookies-store',
             SettingValue(typ.Bool(), 'true'),
             "Whether to store cookies."),

            ('host-block-lists',
             SettingValue(
                 typ.UrlList(none_ok=True),
                 'http://www.malwaredomainlist.com/hostslist/hosts.txt,'
                 'http://someonewhocares.org/hosts/hosts,'
                 'http://winhelp2002.mvps.org/hosts.zip,'
                 'http://malwaredomains.lehigh.edu/files/justdomains.zip,'
                 'http://pgl.yoyo.org/adservers/serverlist.php?'
                 'hostformat=hosts&mimetype=plaintext'),
             "List of URLs of lists which contain hosts to block.\n\n"
             "The file can be in one of the following formats:\n\n"
             "- An '/etc/hosts'-like file\n"
             "- One host per line\n"
             "- A zip-file of any of the above, with either only one file, or "
             "a file named 'hosts' (with any extension)."),

            ('host-blocking-enabled',
             SettingValue(typ.Bool(), 'true'),
             "Whether host blocking is enabled."),

            readonly=readonly
        )),

        ('hints', sect.KeyValue(
            ('border',
             SettingValue(typ.String(), '1px solid #E3BE23'),
             "CSS border value for hints."),

            ('opacity',
             SettingValue(typ.Float(minval=0.0, maxval=1.0), '0.7'),
             "Opacity for hints."),

            ('mode',
             SettingValue(typ.HintMode(), 'letter'),
             "Mode to use for hints."),

            ('chars',
             SettingValue(typ.String(minlen=2), 'asdfghjkl'),
             "Chars used for hint strings."),

            ('min-chars',
             SettingValue(typ.Int(minval=1), '1'),
             "Mininum number of chars used for hint strings."),

            ('scatter',
             SettingValue(typ.Bool(), 'true'),
             "Whether to scatter hint key chains (like Vimium) or not (like "
             "dwb)."),

            ('uppercase',
             SettingValue(typ.Bool(), 'false'),
             "Make chars in hint strings uppercase."),

            ('auto-follow',
             SettingValue(typ.Bool(), 'true'),
             "Whether to auto-follow a hint if there's only one left."),

            ('next-regexes',
             SettingValue(typ.RegexList(flags=re.IGNORECASE),
                          r'\bnext\b,\bmore\b,\bnewer\b,\b[>→≫]\b,\b(>>|»)\b,'
                          r'\bcontinue\b'),
             "A comma-separated list of regexes to use for 'next' links."),

            ('prev-regexes',
             SettingValue(typ.RegexList(flags=re.IGNORECASE),
                          r'\bprev(ious)?\b,\bback\b,\bolder\b,\b[<←≪]\b,'
                          r'\b(<<|«)\b'),
             "A comma-separated list of regexes to use for 'prev' links."),

            readonly=readonly
        )),

        ('searchengines', sect.ValueList(
            typ.SearchEngineName(), typ.SearchEngineUrl(),
            ('DEFAULT', 'https://duckduckgo.com/?q={}'),

            readonly=readonly
        )),

        ('aliases', sect.ValueList(
            typ.String(forbidden=' '), typ.Command(),

            readonly=readonly
        )),

        ('colors', sect.KeyValue(
            ('completion.fg',
             SettingValue(typ.QtColor(), 'white'),
             "Text color of the completion widget."),

            ('completion.bg',
             SettingValue(typ.QssColor(), '#333333'),
             "Background color of the completion widget."),

            ('completion.alternate-bg',
             SettingValue(typ.QssColor(), '#444444'),
             "Alternating background color of the completion widget."),

            ('completion.category.fg',
             SettingValue(typ.QtColor(), 'white'),
             "Foreground color of completion widget category headers."),

            ('completion.category.bg',
             SettingValue(typ.QssColor(), 'qlineargradient(x1:0, y1:0, x2:0, '
                          'y2:1, stop:0 #888888, stop:1 #505050)'),
             "Background color of the completion widget category headers."),

            ('completion.category.border.top',
             SettingValue(typ.QssColor(), 'black'),
             "Top border color of the completion widget category headers."),

            ('completion.category.border.bottom',
             SettingValue(typ.QssColor(), '${completion.category.border.top}'),
             "Bottom border color of the completion widget category headers."),

            ('completion.item.selected.fg',
             SettingValue(typ.QtColor(), 'black'),
             "Foreground color of the selected completion item."),

            ('completion.item.selected.bg',
             SettingValue(typ.QssColor(), '#e8c000'),
             "Background color of the selected completion item."),

            ('completion.item.selected.border.top',
             SettingValue(typ.QssColor(), '#bbbb00'),
             "Top border color of the completion widget category headers."),

            ('completion.item.selected.border.bottom',
             SettingValue(
                 typ.QssColor(), '${completion.item.selected.border.top}'),
             "Bottom border color of the selected completion item."),

            ('completion.match.fg',
             SettingValue(typ.QssColor(), '#ff4444'),
             "Foreground color of the matched text in the completion."),

            ('statusbar.fg',
             SettingValue(typ.QssColor(), 'white'),
             "Foreground color of the statusbar."),

            ('statusbar.bg',
             SettingValue(typ.QssColor(), 'black'),
             "Foreground color of the statusbar."),

            ('statusbar.fg.error',
             SettingValue(typ.QssColor(), '${statusbar.fg}'),
             "Foreground color of the statusbar if there was an error."),

            ('statusbar.bg.error',
             SettingValue(typ.QssColor(), 'red'),
             "Background color of the statusbar if there was an error."),

            ('statusbar.fg.warning',
             SettingValue(typ.QssColor(), '${statusbar.fg}'),
             "Foreground color of the statusbar if there is a warning."),

            ('statusbar.bg.warning',
             SettingValue(typ.QssColor(), 'darkorange'),
             "Background color of the statusbar if there is a warning."),

            ('statusbar.fg.prompt',
             SettingValue(typ.QssColor(), '${statusbar.fg}'),
             "Foreground color of the statusbar if there is a prompt."),

            ('statusbar.bg.prompt',
             SettingValue(typ.QssColor(), 'darkblue'),
             "Background color of the statusbar if there is a prompt."),

            ('statusbar.fg.insert',
             SettingValue(typ.QssColor(), '${statusbar.fg}'),
             "Foreground color of the statusbar in insert mode."),

            ('statusbar.bg.insert',
             SettingValue(typ.QssColor(), 'darkgreen'),
             "Background color of the statusbar in insert mode."),

            ('statusbar.fg.command',
             SettingValue(typ.QssColor(), '${statusbar.fg}'),
             "Foreground color of the statusbar in command mode."),

            ('statusbar.bg.command',
             SettingValue(typ.QssColor(), '${statusbar.bg}'),
             "Background color of the statusbar in command mode."),

            ('statusbar.fg.caret',
             SettingValue(typ.QssColor(), '${statusbar.fg}'),
             "Foreground color of the statusbar in caret mode."),

            ('statusbar.bg.caret',
             SettingValue(typ.QssColor(), 'purple'),
             "Background color of the statusbar in caret mode."),

            ('statusbar.fg.caret-selection',
             SettingValue(typ.QssColor(), '${statusbar.fg}'),
             "Foreground color of the statusbar in caret mode with a "
             "selection"),

            ('statusbar.bg.caret-selection',
             SettingValue(typ.QssColor(), '#a12dff'),
             "Background color of the statusbar in caret mode with a "
             "selection"),

            ('statusbar.progress.bg',
             SettingValue(typ.QssColor(), 'white'),
             "Background color of the progress bar."),

            ('statusbar.url.fg',
             SettingValue(typ.QssColor(), '${statusbar.fg}'),
             "Default foreground color of the URL in the statusbar."),

            ('statusbar.url.fg.success',
             SettingValue(typ.QssColor(), 'lime'),
             "Foreground color of the URL in the statusbar on successful "
             "load."),

            ('statusbar.url.fg.error',
             SettingValue(typ.QssColor(), 'orange'),
             "Foreground color of the URL in the statusbar on error."),

            ('statusbar.url.fg.warn',
             SettingValue(typ.QssColor(), 'yellow'),
             "Foreground color of the URL in the statusbar when there's a "
             "warning."),

            ('statusbar.url.fg.hover',
             SettingValue(typ.QssColor(), 'aqua'),
             "Foreground color of the URL in the statusbar for hovered "
             "links."),

            ('tabs.fg.odd',
             SettingValue(typ.QtColor(), 'white'),
             "Foreground color of unselected odd tabs."),

            ('tabs.bg.odd',
             SettingValue(typ.QtColor(), 'grey'),
             "Background color of unselected odd tabs."),

            ('tabs.fg.even',
             SettingValue(typ.QtColor(), 'white'),
             "Foreground color of unselected even tabs."),

            ('tabs.bg.even',
             SettingValue(typ.QtColor(), 'darkgrey'),
             "Background color of unselected even tabs."),

            ('tabs.fg.selected',
             SettingValue(typ.QtColor(), 'white'),
             "Foreground color of selected tabs."),

            ('tabs.bg.selected',
             SettingValue(typ.QtColor(), 'black'),
             "Background color of selected tabs."),

            ('tabs.bg.bar',
             SettingValue(typ.QtColor(), '#555555'),
             "Background color of the tab bar."),

            ('tabs.indicator.start',
             SettingValue(typ.QtColor(), '#0000aa'),
             "Color gradient start for the tab indicator."),

            ('tabs.indicator.stop',
             SettingValue(typ.QtColor(), '#00aa00'),
             "Color gradient end for the tab indicator."),

            ('tabs.indicator.error',
             SettingValue(typ.QtColor(), '#ff0000'),
             "Color for the tab indicator on errors.."),

            ('tabs.indicator.system',
             SettingValue(typ.ColorSystem(), 'rgb'),
             "Color gradient interpolation system for the tab indicator."),

            ('hints.fg',
             SettingValue(typ.CssColor(), 'black'),
             "Font color for hints."),

            ('hints.bg',
             SettingValue(
                 typ.CssColor(), '-webkit-gradient(linear, left top, '
                 'left bottom, color-stop(0%,#FFF785), '
                 'color-stop(100%,#FFC542))'),
             "Background color for hints."),

            ('hints.fg.match',
             SettingValue(typ.CssColor(), 'green'),
             "Font color for the matched part of hints."),

            ('downloads.bg.bar',
             SettingValue(typ.QssColor(), 'black'),
             "Background color for the download bar."),

            ('downloads.fg.start',
             SettingValue(typ.QtColor(), 'white'),
             "Color gradient start for download text."),

            ('downloads.bg.start',
             SettingValue(typ.QtColor(), '#0000aa'),
             "Color gradient start for download backgrounds."),

            ('downloads.fg.stop',
             SettingValue(typ.QtColor(), '${downloads.fg.start}'),
             "Color gradient end for download text."),

            ('downloads.bg.stop',
             SettingValue(typ.QtColor(), '#00aa00'),
             "Color gradient stop for download backgrounds."),

            ('downloads.fg.system',
             SettingValue(typ.ColorSystem(), 'rgb'),
             "Color gradient interpolation system for download text."),

            ('downloads.bg.system',
             SettingValue(typ.ColorSystem(), 'rgb'),
             "Color gradient interpolation system for download backgrounds."),

            ('downloads.fg.error',
             SettingValue(typ.QtColor(), 'white'),
             "Foreground color for downloads with errors."),

            ('downloads.bg.error',
             SettingValue(typ.QtColor(), 'red'),
             "Background color for downloads with errors."),

            ('webpage.bg',
             SettingValue(typ.QtColor(none_ok=True), 'white'),
             "Background color for webpages if unset (or empty to use the "
             "theme's color)"),

            readonly=readonly
        )),

        ('fonts', sect.KeyValue(
            ('_monospace',
             SettingValue(typ.Font(), 'Terminus, Monospace, '
                          '"DejaVu Sans Mono", Monaco, '
                          '"Bitstream Vera Sans Mono", "Andale Mono", '
                          '"Liberation Mono", "Courier New", Courier, '
                          'monospace, Fixed, Consolas, Terminal'),
             "Default monospace fonts."),

            ('completion',
             SettingValue(typ.Font(), DEFAULT_FONT_SIZE + ' ${_monospace}'),
             "Font used in the completion widget."),

            ('tabbar',
             SettingValue(typ.QtFont(), DEFAULT_FONT_SIZE + ' ${_monospace}'),
             "Font used in the tab bar."),

            ('statusbar',
             SettingValue(typ.Font(), DEFAULT_FONT_SIZE + ' ${_monospace}'),
             "Font used in the statusbar."),

            ('downloads',
             SettingValue(typ.Font(), DEFAULT_FONT_SIZE + ' ${_monospace}'),
             "Font used for the downloadbar."),

            ('hints',
             SettingValue(typ.Font(), 'bold 13px Monospace'),
             "Font used for the hints."),

            ('debug-console',
             SettingValue(typ.QtFont(), DEFAULT_FONT_SIZE + ' ${_monospace}'),
             "Font used for the debugging console."),

            ('web-family-standard',
             SettingValue(typ.FontFamily(none_ok=True), ''),
             "Font family for standard fonts."),

            ('web-family-fixed',
             SettingValue(typ.FontFamily(none_ok=True), ''),
             "Font family for fixed fonts."),

            ('web-family-serif',
             SettingValue(typ.FontFamily(none_ok=True), ''),
             "Font family for serif fonts."),

            ('web-family-sans-serif',
             SettingValue(typ.FontFamily(none_ok=True), ''),
             "Font family for sans-serif fonts."),

            ('web-family-cursive',
             SettingValue(typ.FontFamily(none_ok=True), ''),
             "Font family for cursive fonts."),

            ('web-family-fantasy',
             SettingValue(typ.FontFamily(none_ok=True), ''),
             "Font family for fantasy fonts."),

            ('web-size-minimum',
             SettingValue(
                 typ.Int(none_ok=True, minval=1, maxval=MAXVALS['int']), ''),
             "The hard minimum font size."),

            ('web-size-minimum-logical',
             SettingValue(
                 typ.Int(none_ok=True, minval=1, maxval=MAXVALS['int']), ''),
             "The minimum logical font size that is applied when zooming "
             "out."),

            ('web-size-default',
             SettingValue(
                 typ.Int(none_ok=True, minval=1, maxval=MAXVALS['int']), ''),
             "The default font size for regular text."),

            ('web-size-default-fixed',
             SettingValue(
                 typ.Int(none_ok=True, minval=1, maxval=MAXVALS['int']), ''),
             "The default font size for fixed-pitch text."),

            readonly=readonly
        )),
    ])


DATA = data(readonly=True)


KEY_FIRST_COMMENT = """
# vim: ft=conf
#
# In this config file, qutebrowser's key bindings are configured.
# The format looks like this:
#
# [keymode]
#
# command
#   keychain
#   keychain2
#   ...
#
# All blank lines and lines starting with '#' are ignored.
# Inline-comments are not permitted.
#
# keymode is a comma separated list of modes in which the key binding should be
# active. If keymode starts with !, the key binding is active in all modes
# except the listed modes.
#
# For special keys (can't be part of a keychain), enclose them in `<`...`>`.
# For modifiers, you can use either `-` or `+` as delimiters, and these names:
#
#  * Control: `Control`, `Ctrl`
#  * Meta:    `Meta`, `Windows`, `Mod4`
#  * Alt:     `Alt`, `Mod1`
#  * Shift:   `Shift`
#
# For simple keys (no `<>`-signs), a capital letter means the key is pressed
# with Shift. For special keys (with `<>`-signs), you need to explicitly add
# `Shift-` to match a key pressed with shift.  You can bind multiple commands
# by separating them with `;;`.
"""

KEY_SECTION_DESC = {
    'all': "Keybindings active in all modes.",
    'normal': "Keybindings for normal mode.",
    'insert': (
        "Keybindings for insert mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n\n"
        " * `open-editor`: Open a texteditor with the focused field."),
    'hint': (
        "Keybindings for hint mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n\n"
        " * `follow-hint`: Follow the currently selected hint."),
    'passthrough': (
        "Keybindings for passthrough mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode."),
    'command': (
        "Keybindings for command mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n\n"
        " * `command-history-prev`: Switch to previous command in history.\n"
        " * `command-history-next`: Switch to next command in history.\n"
        " * `completion-item-prev`: Select previous item in completion.\n"
        " * `completion-item-next`: Select next item in completion.\n"
        " * `command-accept`: Execute the command currently in the "
        "commandline."),
    'prompt': (
        "Keybindings for prompts in the status line.\n"
        "You can bind normal keys in this mode, but they will be only active "
        "when a yes/no-prompt is asked. For other prompt modes, you can only "
        "bind special keys.\n"
        "Useful hidden commands to map in this section:\n\n"
        " * `prompt-accept`: Confirm the entered value.\n"
        " * `prompt-yes`: Answer yes to a yes/no question.\n"
        " * `prompt-no`: Answer no to a yes/no question."),
    'caret': (
        ""),
}

# Keys which are similar to Return and should be bound by default where Return
# is bound.

RETURN_KEYS = ['<Return>', '<Ctrl-M>', '<Ctrl-J>', '<Shift-Return>', '<Enter>',
               '<Shift-Enter>']


KEY_DATA = collections.OrderedDict([
    ('!normal', collections.OrderedDict([
        ('clear-keychain ;; leave-mode', ['<Escape>', '<Ctrl-[>']),
    ])),

    ('normal', collections.OrderedDict([
        ('clear-keychain ;; search', ['<Escape>']),
        ('set-cmd-text -s :open', ['o']),
        ('set-cmd-text :open {url}', ['go']),
        ('set-cmd-text -s :open -t', ['O']),
        ('set-cmd-text :open -t {url}', ['gO']),
        ('set-cmd-text -s :open -b', ['xo']),
        ('set-cmd-text :open -b {url}', ['xO']),
        ('set-cmd-text -s :open -w', ['wo']),
        ('set-cmd-text :open -w {url}', ['wO']),
        ('open -t', ['ga', '<Ctrl-T>']),
        ('tab-close', ['d', '<Ctrl-W>']),
        ('tab-close -o', ['D']),
        ('tab-only', ['co']),
        ('tab-focus', ['T']),
        ('tab-move', ['gm']),
        ('tab-move -', ['gl']),
        ('tab-move +', ['gr']),
        ('tab-focus', ['J', 'gt']),
        ('tab-prev', ['K', 'gT']),
        ('tab-clone', ['gC']),
        ('reload', ['r']),
        ('reload -f', ['R']),
        ('back', ['H']),
        ('back -t', ['th']),
        ('back -w', ['wh']),
        ('forward', ['L']),
        ('forward -t', ['tl']),
        ('forward -w', ['wl']),
        ('fullscreen', ['<F11>']),
        ('hint', ['f']),
        ('hint all tab', ['F']),
        ('hint all window', ['wf']),
        ('hint all tab-bg', [';b']),
        ('hint all tab-fg', [';f']),
        ('hint all hover', [';h']),
        ('hint images', [';i']),
        ('hint images tab', [';I']),
        ('hint images tab-bg', ['.i']),
        ('hint links fill ":open {hint-url}"', [';o']),
        ('hint links fill ":open -t {hint-url}"', [';O']),
        ('hint links fill ":open -b {hint-url}"', ['.o']),
        ('hint links yank', [';y']),
        ('hint links yank-primary', [';Y']),
        ('hint --rapid links tab-bg', [';r']),
        ('hint --rapid links window', [';R']),
        ('hint links download', [';d']),
        ('scroll left', ['h']),
        ('scroll down', ['j']),
        ('scroll up', ['k']),
        ('scroll right', ['l']),
        ('undo', ['u', '<Ctrl-Shift-T>']),
        ('scroll-perc 0', ['gg']),
        ('scroll-perc', ['G']),
        ('search-next', ['n']),
        ('search-prev', ['N']),
        ('enter-mode insert', ['i']),
        ('enter-mode caret', ['v']),
        ('yank', ['yy']),
        ('yank -s', ['yY']),
        ('yank -t', ['yt']),
        ('yank -ts', ['yT']),
        ('yank -d', ['yd']),
        ('yank -ds', ['yD']),
        ('paste', ['pp']),
        ('paste -s', ['pP']),
        ('paste -t', ['Pp']),
        ('paste -ts', ['PP']),
        ('paste -w', ['wp']),
        ('paste -ws', ['wP']),
        ('quickmark-save', ['m']),
        ('set-cmd-text -s :quickmark-load', ['b']),
        ('set-cmd-text -s :quickmark-load -t', ['B']),
        ('set-cmd-text -s :quickmark-load -w', ['wb']),
        ('bookmark-add', ['M']),
        ('set-cmd-text -s :bookmark-load', ['gb']),
        ('set-cmd-text -s :bookmark-load -t', ['gB']),
        ('set-cmd-text -s :bookmark-load -w', ['wB']),
        ('save', ['sf']),
        ('set-cmd-text -s :set', ['ss']),
        ('set-cmd-text -s :set -t', ['sl']),
        ('set-cmd-text -s :set keybind', ['sk']),
        ('zoom-out', ['-']),
        ('zoom-in', ['+']),
        ('zoom', ['=']),
        ('navigate prev', ['[[']),
        ('navigate next', [']]']),
        ('navigate prev -t', ['{{']),
        ('navigate next -t', ['}}']),
        ('navigate up', ['gu']),
        ('navigate up -t', ['gU']),
        ('navigate increment', ['<Ctrl-A>']),
        ('navigate decrement', ['<Ctrl-X>']),
        ('inspector', ['wi']),
        ('download', ['gd']),
        ('download-cancel', ['ad']),
        ('download-remove --all', ['cd']),
        ('view-source', ['gf']),
        ('tab-focus last', ['<Ctrl-Tab>']),
        ('enter-mode passthrough', ['<Ctrl-V>']),
        ('quit', ['<Ctrl-Q>']),
        ('scroll-page 0 1', ['<Ctrl-F>']),
        ('scroll-page 0 -1', ['<Ctrl-B>']),
        ('scroll-page 0 0.5', ['<Ctrl-D>']),
        ('scroll-page 0 -0.5', ['<Ctrl-U>']),
        ('tab-focus 1', ['<Alt-1>']),
        ('tab-focus 2', ['<Alt-2>']),
        ('tab-focus 3', ['<Alt-3>']),
        ('tab-focus 4', ['<Alt-4>']),
        ('tab-focus 5', ['<Alt-5>']),
        ('tab-focus 6', ['<Alt-6>']),
        ('tab-focus 7', ['<Alt-7>']),
        ('tab-focus 8', ['<Alt-8>']),
        ('tab-focus 9', ['<Alt-9>']),
        ('home', ['<Ctrl-h>']),
        ('stop', ['<Ctrl-s>']),
        ('print', ['<Ctrl-Alt-p>']),
        ('open qute:settings', ['Ss']),
        ('follow-selected', RETURN_KEYS),
        ('follow-selected -t', ['<Ctrl-Return>', '<Ctrl-Enter>']),
    ])),

    ('insert', collections.OrderedDict([
        ('open-editor', ['<Ctrl-E>']),
    ])),

    ('hint', collections.OrderedDict([
        ('follow-hint', RETURN_KEYS),
        ('hint --rapid links tab-bg', ['<Ctrl-R>']),
        ('hint links', ['<Ctrl-F>']),
        ('hint all tab-bg', ['<Ctrl-B>']),
    ])),

    ('passthrough', {}),

    ('command', collections.OrderedDict([
        ('command-history-prev', ['<Ctrl-P>']),
        ('command-history-next', ['<Ctrl-N>']),
        ('completion-item-prev', ['<Shift-Tab>', '<Up>']),
        ('completion-item-next', ['<Tab>', '<Down>']),
        ('completion-item-del', ['<Ctrl-D>']),
        ('command-accept', RETURN_KEYS),
    ])),

    ('prompt', collections.OrderedDict([
        ('prompt-accept', RETURN_KEYS),
        ('prompt-yes', ['y']),
        ('prompt-no', ['n']),
    ])),

    ('command,prompt', collections.OrderedDict([
        ('rl-backward-char', ['<Ctrl-B>']),
        ('rl-forward-char', ['<Ctrl-F>']),
        ('rl-backward-word', ['<Alt-B>']),
        ('rl-forward-word', ['<Alt-F>']),
        ('rl-beginning-of-line', ['<Ctrl-A>']),
        ('rl-end-of-line', ['<Ctrl-E>']),
        ('rl-unix-line-discard', ['<Ctrl-U>']),
        ('rl-kill-line', ['<Ctrl-K>']),
        ('rl-kill-word', ['<Alt-D>']),
        ('rl-unix-word-rubout', ['<Ctrl-W>', '<Alt-Backspace>']),
        ('rl-yank', ['<Ctrl-Y>']),
        ('rl-delete-char', ['<Ctrl-?>']),
        ('rl-backward-delete-char', ['<Ctrl-H>']),
    ])),

    ('caret', collections.OrderedDict([
        ('toggle-selection', ['v', '<Space>']),
        ('drop-selection', ['<Ctrl-Space>']),
        ('enter-mode normal', ['c']),
        ('move-to-next-line', ['j']),
        ('move-to-prev-line', ['k']),
        ('move-to-next-char', ['l']),
        ('move-to-prev-char', ['h']),
        ('move-to-end-of-word', ['e']),
        ('move-to-next-word', ['w']),
        ('move-to-prev-word', ['b']),
        ('move-to-start-of-next-block', [']']),
        ('move-to-start-of-prev-block', ['[']),
        ('move-to-end-of-next-block', ['}']),
        ('move-to-end-of-prev-block', ['{']),
        ('move-to-start-of-line', ['0']),
        ('move-to-end-of-line', ['$']),
        ('move-to-start-of-document', ['gg']),
        ('move-to-end-of-document', ['G']),
        ('yank-selected -p', ['Y']),
        ('yank-selected', ['y'] + RETURN_KEYS),
        ('scroll left', ['H']),
        ('scroll down', ['J']),
        ('scroll up', ['K']),
        ('scroll right', ['L']),
    ])),
])


# A list of (regex, replacement) tuples of changed key commands.

CHANGED_KEY_COMMANDS = [
    (re.compile(r'^open -([twb]) about:blank$'), r'open -\1'),

    (re.compile(r'^download-page$'), r'download'),
    (re.compile(r'^cancel-download$'), r'download-cancel'),

    (re.compile(r"""^search (''|"")$"""), r'clear-keychain ;; search'),
    (re.compile(r'^search$'), r'clear-keychain ;; search'),

    (re.compile(r"""^set-cmd-text ['"](.*) ['"]$"""), r'set-cmd-text -s \1'),
    (re.compile(r"""^set-cmd-text ['"](.*)['"]$"""), r'set-cmd-text \1'),

    (re.compile(r"^hint links rapid$"), r'hint --rapid links tab-bg'),
    (re.compile(r"^hint links rapid-win$"), r'hint --rapid links window'),

    (re.compile(r'^scroll -50 0$'), r'scroll left'),
    (re.compile(r'^scroll 0 50$'), r'scroll down'),
    (re.compile(r'^scroll 0 -50$'), r'scroll up'),
    (re.compile(r'^scroll 50 0$'), r'scroll right'),
    (re.compile(r'^scroll ([-\d]+ [-\d]+)$'), r'scroll-px \1'),

    (re.compile(r'^search *;; *clear-keychain$'), r'clear-keychain ;; search'),
    (re.compile(r'^leave-mode$'), r'clear-keychain ;; leave-mode'),
]
