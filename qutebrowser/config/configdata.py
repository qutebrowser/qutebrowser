# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
DATA: The config defaults, an OrderedDict of sections.
"""

from collections import OrderedDict

from qutebrowser.config._value import SettingValue
import qutebrowser.config._conftypes as types
import qutebrowser.config._sections as sect


FIRST_COMMENT = """
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
# This is the default config, so if you want to remove anything from
# here (as opposed to change/add), for example a keybinding, set it to
# an empty value.
"""


SECTION_DESC = {
    'general': "General/misc. options",
    'input': "Options related to input modes.",
    'completion': "Options related to completion and command history .",
    'tabbar': "Configuration of the tab bar.",
    'webkit': "Webkit settings.",
    'hints': "Hinting settings.",
    'searchengines': (
        "Definitions of search engines which can be used via the address "
        "bar.\n"
        "The searchengine named DEFAULT is used when general.auto-search "
        "is true and something else than an URL was entered to be opened. "
        "Other search engines can be used via the bang-syntax, e.g. "
        "\"qutebrowser !google\". The string \"{}\" will be replaced by the "
        "search term, use \"{{\" and \"}}\" for literal {/} signs."),
    'keybind': (
        "Bindings from a key(chain) to a command.\n"
        "For special keys (can't be part of a keychain), enclose them in "
        "<...>. For modifiers, you can use either - or + as delimiters, and "
        "these names:\n"
        "  Control: Control, Ctrl\n"
        "  Meta:    Meta, Windows, Mod4\n"
        "  Alt:     Alt, Mod1\n"
        "  Shift:   Shift\n"
        "For simple keys (no <>-signs), a capital letter means the key is "
        "pressed with Shift. For special keys (with <>-signs), you need "
        "to explicitely add \"Shift-\" to match a key pressed with shift. "
        "You can bind multiple commands by separating them with \";;\"."),
    'keybind.insert': (
        "Keybindings for insert mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n"
        "  open_editor: Open a texteditor with the focused field.\n"
        "  leave_mode: Leave the command mode."),
    'keybind.hint': (
        "Keybindings for hint mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n"
        "  follow_hint: Follow the currently selected hint.\n"
        "  leave_mode: Leave the command mode."),
    'keybind.passthrough': (
        "Keybindings for hint mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "An useful command to map here is the hidden command leave_mode."),
    'keybind.command': (
        "Keybindings for command mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n"
        "  command_history_prev: Switch to previous command in history.\n"
        "  command_history_next: Switch to next command in history.\n"
        "  completion_item_prev: Select previous item in completion.\n"
        "  completion_item_next: Select next item in completion.\n"
        "  command_accept: Execute the command currently in the commandline.\n"
        "  leave_mode: Leave the command mode."),
    'aliases': (
        "Aliases for commands.\n"
        "By default, no aliases are defined. Example which adds a new command "
        ":qtb to open qutebrowsers website:\n"
        "  qtb = open http://www.qutebrowser.org/"),
    'colors': (
        "Colors used in the UI.\n"
        "A value can be in one of the following format:\n"
        "  - #RGB/#RRGGBB/#RRRGGGBBB/#RRRRGGGGBBBB\n"
        "  - A SVG color name as specified in [1].\n"
        "  - transparent (no color)\n"
        "  - rgb(r, g, b) / rgba(r, g, b, a) (values 0-255 or "
        "percentages)\n"
        "  - hsv(h, s, v) / hsva(h, s, v, a) (values 0-255, hue 0-359)\n"
        "  - A gradient as explained at [2] under \"Gradient\"\n"
        "  [1] http://www.w3.org/TR/SVG/types.html#ColorKeywords\n"
        "  [2] http://qt-project.org/doc/qt-4.8/stylesheet-reference.html"
        "#list-of-property-types\n"
        "The \"hints.*\" values are a special case as they're real CSS "
        "colors, not Qt-CSS colors. There, for a gradient, you need to use "
        "-webkit-gradient, see [3].\n"
        "  [3] https://www.webkit.org/blog/175/introducing-css-gradients/"),
    'fonts': (
        "Fonts used for the UI, with optional style/weight/size.\n"
        "  Style: normal/italic/oblique\n"
        "  Weight: normal, bold, 100..900\n"
        "  Size: Number + px/pt\n"
        "Note: The font for hints is a true CSS font, not a Qt-CSS one, "
        "because of that, a general \"Monospace\" family is enough and we "
        "don't use \"${_monospace}\" there."),
}


DATA = OrderedDict([
    ('general', sect.KeyValue(
        ('ignore-case',
         SettingValue(types.Bool(), 'true'),
         "Whether to do case-insensitive searching."),

        ('wrap-search',
         SettingValue(types.Bool(), 'true'),
         "Whether to wrap search to the top when arriving at the end."),

        ('startpage',
         SettingValue(types.List(), 'http://www.duckduckgo.com'),
         "The default page(s) to open at the start, separated with commas."),

        ('auto-search',
         SettingValue(types.AutoSearch(), 'naive'),
         "Whether to start a search when something else than an URL is "
         "entered."),

        ('zoom-levels',
         SettingValue(types.PercList(minval=0),
                      '25%,33%,50%,67%,75%,90%,100%,110%,125%,150%,175%,200%,'
                      '250%,300%,400%,500%'),
         "The available zoom levels, separated by commas."),

        ('default-zoom',
         SettingValue(types.ZoomPerc(), '100%'),
         "The default zoom level."),

        ('auto-save-config',
         SettingValue(types.Bool(), 'true'),
         "Whether to save the config automatically on quit."),

        ('background-tabs',
         SettingValue(types.Bool(), 'false'),
         "Whether to open new tabs (middleclick/ctrl+click) in background"),

        ('editor',
         SettingValue(types.ShellCommand(placeholder=True), 'gvim -f "{}"'),
         "The editor (and arguments) to use for the open_editor binding. "
         "Use {} for the filename. Gets split via shutils."),
    )),

    ('completion', sect.KeyValue(
        ('show',
         SettingValue(types.Bool(), 'true'),
         "Whether to show the autocompletion window or not."),

        ('height',
         SettingValue(types.PercOrInt(minperc=0, maxperc=100, minint=1),
                      '50%'),
         "The height of the completion, in px or as percentage of the "
         "window."),

        ('history-length',
         SettingValue(types.Int(minval=-1), '100'),
         "How many commands to save in the history. 0: no history / -1: "
         "unlimited"),

    )),

    ('input', sect.KeyValue(
        ('timeout',
         SettingValue(types.Int(minval=0), '500'),
         "Timeout for ambiguous keybindings."),

        ('insert-mode-on-plugins',
         SettingValue(types.Bool(), 'true'),
         "Whether to switch to insert mode when clicking flash and other "
         "plugins."),

        ('auto-insert-mode',
         SettingValue(types.Bool(), 'true'),
         "Whether to automatically enter insert mode if an editable element "
         "is focused after page load."),

        ('forward-unbound-keys',
         SettingValue(types.Bool(), 'false'),
         "Whether to forward unbound keys to the website in normal mode."),
    )),

    ('tabbar', sect.KeyValue(
        ('movable',
         SettingValue(types.Bool(), 'true'),
         "Whether tabs should be movable."),

        ('close-buttons',
         SettingValue(types.Bool(), 'false'),
         "Whether tabs should have close-buttons."),

        ('scroll-buttons',
         SettingValue(types.Bool(), 'true'),
         "Whether there should be scroll buttons if there are too many tabs."),

        ('position',
         SettingValue(types.Position(), 'north'),
         "The position of the tab bar."),

        ('select-on-remove',
         SettingValue(types.SelectOnRemove(), 'previous'),
         "Which tab to select when the focused tab is removed."),

        ('last-close',
         SettingValue(types.LastClose(), 'ignore'),
         "Behaviour when the last tab is closed."),

        ('wrap',
         SettingValue(types.Bool(), 'true'),
         "Whether to wrap when changing tabs."),
    )),

    ('webkit', sect.KeyValue(
        ('auto-load-images',
         SettingValue(types.Bool(), 'true'),
         "Specifies whether images are automatically loaded in web pages."),

        ('dns-prefetch-enabled',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether QtWebkit will try to pre-fetch DNS entries to "
         "speed up browsing."),

        ('javascript-enabled',
         SettingValue(types.Bool(), 'true'),
         "Enables or disables the running of JavaScript programs."),

        #('java-enabled',
        # SettingValue(types.Bool(), 'true'),
        # "Enables or disables Java applets. Currently Java applets are "
        # "not supported"),

        ('plugins-enabled',
         SettingValue(types.Bool(), 'false'),
         "Enables or disables plugins in Web pages"),

        ('private-browsing-enabled',
         SettingValue(types.Bool(), 'false'),
         "Private browsing prevents WebKit from recording visited pages in "
         "the history and storing web page icons."),

        ('javascript-can-open-windows',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether JavaScript programs can open new windows."),

        ('javascript-can-close-windows',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether JavaScript programs can close windows."),

        ('javascript-can-access-clipboard',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether JavaScript programs can read or write to the "
         "clipboard."),

        ('developer-extras-enabled',
         SettingValue(types.Bool(), 'false'),
         "Enables extra tools for Web developers (e.g. webinspector)"),

        ('spatial-navigation-enabled',
         SettingValue(types.Bool(), 'false'),
         "Enables or disables the Spatial Navigation feature, which consists "
         "in the ability to navigate between focusable elements in a Web "
         "page, such as hyperlinks and form controls, by using Left, Right, "
         "Up and Down arrow keys."),

        ('links-included-in-focus-chain',
         SettingValue(types.Bool(), 'true'),
         "Specifies whether hyperlinks should be included in the keyboard "
         "focus chain."),

        ('zoom-text-only',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether the zoom factor on a frame applies only to the "
         "text or to all content."),

        ('print-element-backgrounds',
         SettingValue(types.Bool(), 'true'),
         "Specifies whether the background color and images are also drawn "
         "when the page is printed. "),

        ('offline-storage-database-enabled',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether support for the HTML 5 offline storage feature is "
         "enabled or not. "),

        ('offline-web-application-storage-enabled',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether support for the HTML 5 web application cache "
         "feature is enabled or not. "),

        ('local-storage-enabled',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether support for the HTML 5 local storage feature is "
         "enabled or not."),

        ('local-content-can-access-remote-urls',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether locally loaded documents are allowed to access "
         "remote urls."),

        ('local-content-can-access-file-urls',
         SettingValue(types.Bool(), 'true'),
         "Specifies whether locally loaded documents are allowed to access "
         "other local urls."),

        ('xss-auditing-enabled',
         SettingValue(types.Bool(), 'false'),
         "Specifies whether load requests should be monitored for cross-site "
         "scripting attempts. Suspicious scripts will be blocked and reported "
         "in the inspector's JavaScript console. Enabling this feature might "
         "have an impact on performance."),

        #('accelerated-compositing-enabled',
        # SettingValue(types.Bool(), 'true'),
        # "This feature, when used in conjunction with QGraphicsWebView, "
        # "accelerates animations of web content. CSS animations of the "
        # "transform and opacity properties will be rendered by composing the "
        # "cached content of the animated elements. "),

        #('tiled-backing-store-enabled',
        # SettingValue(types.Bool(), 'false'),
        # "This setting enables the tiled backing store feature for a "
        # "QGraphicsWebView. With the tiled backing store enabled, the web "
        # "page contents in and around the current visible area is "
        # "speculatively cached to bitmap tiles. The tiles are automatically "
        # "kept in sync with the web page as it changes. Enabling tiling can "
        # "significantly speed up painting heavy operations like scrolling. "
        # "Enabling the feature increases memory consuption."),

        ('frame-flattening-enabled',
         SettingValue(types.Bool(), 'false'),
         "With this setting each subframe is expanded to its contents. This "
         "will flatten all the frames to become one scrollable "
         "page."),

        ('site-specific-quirks-enabled',
         SettingValue(types.Bool(), 'true'),
         "This setting enables WebKit's workaround for broken sites."),
    )),

    ('hints', sect.KeyValue(
        ('border',
         SettingValue(types.String(), '1px solid #E3BE23'),
         "CSS border value for hints."),

        ('opacity',
         SettingValue(types.Float(minval=0.0, maxval=1.0), '0.7'),
         "Opacity for hints."),

        ('chars',
         SettingValue(types.String(minlen=2), 'asdfghjkl'),
         "Chars used for hint strings."),

        ('auto-follow',
         SettingValue(types.Bool(), 'true'),
         "Whether to auto-follow a hint if there's only one left."),
    )),

    ('searchengines', sect.ValueList(
        types.SearchEngineName(), types.SearchEngineUrl(),
        ('DEFAULT', '${duckduckgo}'),
        ('duckduckgo', 'https://duckduckgo.com/?q={}'),
        ('ddg', '${duckduckgo}'),
        ('google', 'https://encrypted.google.com/search?q={}'),
        ('g', '${google}'),
        ('wikipedia', 'http://en.wikipedia.org/w/index.php?'
                      'title=Special:Search&search={}'),
        ('wiki', '${wikipedia}'),
    )),

    ('keybind', sect.ValueList(
        types.KeyBindingName(), types.KeyBinding(),
        ('o', 'open'),
        ('go', 'opencur'),
        ('O', 'tabopen'),
        ('gO', 'tabopencur'),
        ('ga', 'tabopen about:blank'),
        ('d', 'tabclose'),
        ('J', 'tabnext'),
        ('K', 'tabprev'),
        ('r', 'reload'),
        ('H', 'back'),
        ('L', 'forward'),
        ('f', 'hint'),
        ('F', 'hint all tab'),
        (';b', 'hint all bgtab'),
        (';i', 'hint images'),
        (';I', 'hint images tab'),
        ('.i', 'hint images bgtab'),
        (';e', 'hint editable'),
        (';o', 'hint links cmd'),
        (';O', 'hint links cmd_tab'),
        ('.o', 'hint links cmd_bgtab'),
        (';y', 'hint links yank'),
        (';Y', 'hint links yank_primary'),
        (';r', 'hint links rapid'),
        ('h', 'scroll -50 0'),
        ('j', 'scroll 0 50'),
        ('k', 'scroll 0 -50'),
        ('l', 'scroll 50 0'),
        ('u', 'undo'),
        ('gg', 'scroll_perc_y 0'),
        ('G', 'scroll_perc_y'),
        ('n', 'nextsearch'),
        ('i', 'enter_mode insert'),
        ('yy', 'yank'),
        ('yY', 'yank sel'),
        ('yt', 'yanktitle'),
        ('yT', 'yanktitle sel'),
        ('pp', 'paste'),
        ('pP', 'paste sel'),
        ('Pp', 'tabpaste'),
        ('PP', 'tabpaste sel'),
        ('-', 'zoomout'),
        ('+', 'zoomin'),
        ('<Ctrl-V>', 'enter_mode passthrough'),
        ('<Ctrl-Q>', 'quit'),
        ('<Ctrl-Shift-T>', 'undo'),
        ('<Ctrl-W>', 'tabclose'),
        ('<Ctrl-T>', 'tabopen about:blank'),
        ('<Ctrl-F>', 'scroll_page 0 1'),
        ('<Ctrl-B>', 'scroll_page 0 -1'),
        ('<Ctrl-D>', 'scroll_page 0 0.5'),
        ('<Ctrl-U>', 'scroll_page 0 -0.5'),
        ('<Backspace>', 'back'),
        ('<Left>', '${h}'),
        ('<Down>', '${k}'),
        ('<Up>', '${j}'),
        ('<Right>', '${l}'),
    )),

    ('keybind.insert', sect.ValueList(
        types.KeyBindingName(), types.KeyBinding(),
        ('<Escape>', 'leave_mode'),
        ('<Ctrl-E>', 'open_editor'),
    )),

    ('keybind.hint', sect.ValueList(
        types.KeyBindingName(), types.KeyBinding(),
        ('<Return>', 'follow_hint'),
        ('<Escape>', 'leave_mode'),
        ('<Ctrl-C>', 'leave_mode'),
    )),

    ('keybind.passthrough', sect.ValueList(
        types.KeyBindingName(), types.KeyBinding(),
        ('<Escape>', 'leave_mode'),
    )),

    ('keybind.command', sect.ValueList(
        types.KeyBindingName(), types.KeyBinding(),
        ('<Escape>', 'leave_mode'),
        ('<Up>', 'command_history_prev'),
        ('<Down>', 'command_history_next'),
        ('<Shift-Tab>', 'completion_item_prev'),
        ('<Tab>', 'completion_item_next'),
        ('<Return>', 'command_accept'),
    )),

    ('aliases', sect.ValueList(
        types.Command(), types.Command(),
    )),

    ('colors', sect.KeyValue(
        ('completion.fg',
         SettingValue(types.Color(), '#333333'),
         "Text color of the completion widget."),

        ('completion.item.bg',
         SettingValue(types.Color(), 'white'),
         "Background color of completion widget items."),

        ('completion.category.bg',
         SettingValue(types.Color(), 'qlineargradient(x1:0, y1:0, x2:0, y2:1, '
                      'stop:0 #e4e4e4, stop:1 #dbdbdb)'),
         "Background color of the completion widget category headers."),

        ('completion.category.border.top',
         SettingValue(types.Color(), '#808080'),
         "Top border color of the completion widget category headers."),

        ('completion.category.border.bottom',
         SettingValue(types.Color(), '#bbbbbb'),
         "Bottom border color of the completion widget category headers."),

        ('completion.item.selected.fg',
         SettingValue(types.Color(), '#333333'),
         "Foreground color of the selected completion item."),

        ('completion.item.selected.bg',
         SettingValue(types.Color(), '#ffec8b'),
         "Background color of the selected completion item."),

        ('completion.item.selected.border.top',
         SettingValue(types.Color(), '#f2f2c0'),
         "Top border color of the completion widget category headers."),

        ('completion.item.selected.border.bottom',
         SettingValue(types.Color(), '#ffec8b'),
         "Bottom border color of the selected completion item."),

        ('completion.match.fg',
         SettingValue(types.Color(), 'red'),
         "Foreground color of the matched text in the completion."),

        ('statusbar.bg',
         SettingValue(types.Color(), 'black'),
         "Foreground color of the statusbar."),

        ('statusbar.fg',
         SettingValue(types.Color(), 'white'),
         "Foreground color of the statusbar."),

        ('statusbar.bg.error',
         SettingValue(types.Color(), 'red'),
         "Background color of the statusbar if there was an error."),

        ('statusbar.fg.error',
         SettingValue(types.Color(), '${statusbar.fg}'),
         "Foreground color of the statusbar if there was an error."),

        ('statusbar.progress.bg',
         SettingValue(types.Color(), 'white'),
         "Background color of the progress bar."),

        ('statusbar.url.fg',
         SettingValue(types.Color(), '${statusbar.fg}'),
         "Default foreground color of the URL in the statusbar."),

        ('statusbar.url.fg.success',
         SettingValue(types.Color(), 'lime'),
         "Foreground color of the URL in the statusbar on successful "
         "load."),

        ('statusbar.url.fg.error',
         SettingValue(types.Color(), 'orange'),
         "Foreground color of the URL in the statusbar on error."),

        ('statusbar.url.fg.warn',
         SettingValue(types.Color(), 'yellow'),
         "Foreground color of the URL in the statusbar when there's a "
         "warning."),

        ('statusbar.url.fg.hover',
         SettingValue(types.Color(), 'aqua'),
         "Foreground color of the URL in the statusbar for hovered "
         "links."),

        ('tab.fg',
         SettingValue(types.Color(), 'white'),
         "Foreground color of tabs."),

        ('tab.bg',
         SettingValue(types.Color(), 'grey'),
         "Background color of unselected tabs."),

        ('tab.bg.selected',
         SettingValue(types.Color(), 'black'),
         "Background color of selected tabs."),

        ('tab.bg.bar',
         SettingValue(types.Color(), '#555555'),
         "Background color of the tabbar."),

        ('tab.seperator',
         SettingValue(types.Color(), '#555555'),
         "Color for the tab seperator."),

        ('hints.fg',
         SettingValue(types.CssColor(), 'black'),
         "Font color for hints."),

        ('hints.fg.match',
         SettingValue(types.CssColor(), 'green'),
         "Font color for the matched part of hints."),

        ('hints.bg',
         SettingValue(types.CssColor(), '-webkit-gradient(linear, left top, '
                                        'left bottom, color-stop(0%,#FFF785), '
                                        'color-stop(100%,#FFC542))'),
         "Background color for hints."),
    )),

    ('fonts', sect.KeyValue(
        ('_monospace',
         SettingValue(types.Font(), 'Monospace, "DejaVu Sans Mono", Consolas, '
                      'Monaco, "Bitstream Vera Sans Mono", "Andale Mono", '
                      '"Liberation Mono", "Courier New", Courier, monospace, '
                      'Fixed, Terminal'),
         "Default monospace fonts."),

        ('completion',
         SettingValue(types.Font(), '8pt ${_monospace}'),
         "Font used in the completion widget."),

        ('tabbar',
         SettingValue(types.Font(), '8pt ${_monospace}'),
         "Font used in the tabbar."),

        ('statusbar',
         SettingValue(types.Font(), '8pt ${_monospace}'),
         "Font used in the statusbar."),

        ('hints',
         SettingValue(types.Font(), 'bold 12px Monospace'),
         "Font used for the hints."),
    )),
])
