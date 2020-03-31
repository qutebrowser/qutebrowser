# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Code to show a diff of the legacy config format."""

import typing
import difflib
import os.path

import pygments
import pygments.lexers
import pygments.formatters

from qutebrowser.utils import standarddir


OLD_CONF = """
[general]
ignore-case = smart
startpage = https://start.duckduckgo.com
yank-ignored-url-parameters = ref,utm_source,utm_medium,utm_campaign,utm_term,utm_content
default-open-dispatcher =
default-page = ${startpage}
auto-search = naive
auto-save-config = true
auto-save-interval = 15000
editor = gvim -f "{}"
editor-encoding = utf-8
private-browsing = false
developer-extras = false
print-element-backgrounds = true
xss-auditing = false
default-encoding = iso-8859-1
new-instance-open-target = tab
new-instance-open-target.window = last-focused
log-javascript-console = debug
save-session = false
session-default-name =
url-incdec-segments = path,query
[ui]
history-session-interval = 30
zoom-levels = 25%,33%,50%,67%,75%,90%,100%,110%,125%,150%,175%,200%,250%,300%,400%,500%
default-zoom = 100%
downloads-position = top
status-position = bottom
message-timeout = 2000
message-unfocused = false
confirm-quit = never
zoom-text-only = false
frame-flattening = false
user-stylesheet =
hide-scrollbar = true
smooth-scrolling = false
remove-finished-downloads = -1
hide-statusbar = false
statusbar-padding = 1,1,0,0
window-title-format = {perc}{title}{title_sep}qutebrowser
modal-js-dialog = false
hide-wayland-decoration = false
keyhint-blacklist =
keyhint-delay = 500
prompt-radius = 8
prompt-filebrowser = true
[network]
do-not-track = true
accept-language = en-US,en
referer-header = same-domain
user-agent =
proxy = system
proxy-dns-requests = true
ssl-strict = ask
dns-prefetch = true
custom-headers =
netrc-file =
[completion]
show = always
download-path-suggestion = path
timestamp-format = %Y-%m-%d
height = 50%
cmd-history-max-items = 100
web-history-max-items = -1
quick-complete = true
shrink = false
scrollbar-width = 12
scrollbar-padding = 2
[input]
timeout = 500
partial-timeout = 5000
insert-mode-on-plugins = false
auto-leave-insert-mode = true
auto-insert-mode = false
forward-unbound-keys = auto
spatial-navigation = false
links-included-in-focus-chain = true
rocker-gestures = false
mouse-zoom-divider = 512
[tabs]
background-tabs = false
select-on-remove = next
new-tab-position = next
new-tab-position-explicit = last
last-close = ignore
show = always
show-switching-delay = 800
wrap = true
movable = true
close-mouse-button = middle
position = top
show-favicons = true
favicon-scale = 1.0
width = 20%
pinned-width = 43
indicator-width = 3
tabs-are-windows = false
title-format = {index}: {title}
title-format-pinned = {index}
title-alignment = left
mousewheel-tab-switching = true
padding = 0,0,5,5
indicator-padding = 2,2,0,4
[storage]
download-directory =
prompt-download-directory = true
remember-download-directory = true
maximum-pages-in-cache = 0
offline-web-application-cache = true
local-storage = true
cache-size =
[content]
allow-images = true
allow-javascript = true
allow-plugins = false
webgl = true
hyperlink-auditing = false
geolocation = ask
notifications = ask
media-capture = ask
javascript-can-open-windows-automatically = false
javascript-can-close-windows = false
javascript-can-access-clipboard = false
ignore-javascript-prompt = false
ignore-javascript-alert = false
local-content-can-access-remote-urls = false
local-content-can-access-file-urls = true
cookies-accept = no-3rdparty
cookies-store = true
host-block-lists = https://www.malwaredomainlist.com/hostslist/hosts.txt,http://someonewhocares.org/hosts/hosts,http://winhelp2002.mvps.org/hosts.zip,http://malwaredomains.lehigh.edu/files/justdomains.zip,https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&mimetype=plaintext
host-blocking-enabled = true
host-blocking-whitelist = piwik.org
enable-pdfjs = false
[hints]
border = 1px solid #E3BE23
mode = letter
chars = asdfghjkl
min-chars = 1
scatter = true
uppercase = false
dictionary = /usr/share/dict/words
auto-follow = unique-match
auto-follow-timeout = 0
next-regexes = \\bnext\\b,\\bmore\\b,\\bnewer\\b,\\b[>\u2192\u226b]\\b,\\b(>>|\xbb)\\b,\\bcontinue\\b
prev-regexes = \\bprev(ious)?\\b,\\bback\\b,\\bolder\\b,\\b[<\u2190\u226a]\\b,\\b(<<|\xab)\\b
find-implementation = python
hide-unmatched-rapid-hints = true
[searchengines]
DEFAULT = https://duckduckgo.com/?q={}
[aliases]
[colors]
completion.fg = white
completion.bg = #333333
completion.alternate-bg = #444444
completion.category.fg = white
completion.category.bg = qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #888888, stop:1 #505050)
completion.category.border.top = black
completion.category.border.bottom = ${completion.category.border.top}
completion.item.selected.fg = black
completion.item.selected.bg = #e8c000
completion.item.selected.border.top = #bbbb00
completion.item.selected.border.bottom = ${completion.item.selected.border.top}
completion.match.fg = #ff4444
completion.scrollbar.fg = ${completion.fg}
completion.scrollbar.bg = ${completion.bg}
statusbar.fg = white
statusbar.bg = black
statusbar.fg.private = ${statusbar.fg}
statusbar.bg.private = #666666
statusbar.fg.insert = ${statusbar.fg}
statusbar.bg.insert = darkgreen
statusbar.fg.command = ${statusbar.fg}
statusbar.bg.command = ${statusbar.bg}
statusbar.fg.command.private = ${statusbar.fg.private}
statusbar.bg.command.private = ${statusbar.bg.private}
statusbar.fg.caret = ${statusbar.fg}
statusbar.bg.caret = purple
statusbar.fg.caret-selection = ${statusbar.fg}
statusbar.bg.caret-selection = #a12dff
statusbar.progress.bg = white
statusbar.url.fg = ${statusbar.fg}
statusbar.url.fg.success = white
statusbar.url.fg.success.https = lime
statusbar.url.fg.error = orange
statusbar.url.fg.warn = yellow
statusbar.url.fg.hover = aqua
tabs.fg.odd = white
tabs.bg.odd = grey
tabs.fg.even = white
tabs.bg.even = darkgrey
tabs.fg.selected.odd = white
tabs.bg.selected.odd = black
tabs.fg.selected.even = ${tabs.fg.selected.odd}
tabs.bg.selected.even = ${tabs.bg.selected.odd}
tabs.bg.bar = #555555
tabs.indicator.start = #0000aa
tabs.indicator.stop = #00aa00
tabs.indicator.error = #ff0000
tabs.indicator.system = rgb
hints.fg = black
hints.bg = qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 247, 133, 0.8), stop:1 rgba(255, 197, 66, 0.8))
hints.fg.match = green
downloads.bg.bar = black
downloads.fg.start = white
downloads.bg.start = #0000aa
downloads.fg.stop = ${downloads.fg.start}
downloads.bg.stop = #00aa00
downloads.fg.system = rgb
downloads.bg.system = rgb
downloads.fg.error = white
downloads.bg.error = red
webpage.bg = white
keyhint.fg = #FFFFFF
keyhint.fg.suffix = #FFFF00
keyhint.bg = rgba(0, 0, 0, 80%)
messages.fg.error = white
messages.bg.error = red
messages.border.error = #bb0000
messages.fg.warning = white
messages.bg.warning = darkorange
messages.border.warning = #d47300
messages.fg.info = white
messages.bg.info = black
messages.border.info = #333333
prompts.fg = white
prompts.bg = darkblue
prompts.selected.bg = #308cc6
[fonts]
_monospace = xos4 Terminus, Terminus, Monospace, "DejaVu Sans Mono", Monaco, "Bitstream Vera Sans Mono", "Andale Mono", "Courier New", Courier, "Liberation Mono", monospace, Fixed, Consolas, Terminal
completion = 8pt ${_monospace}
completion.category = bold ${completion}
tabbar = 8pt ${_monospace}
statusbar = 8pt ${_monospace}
downloads = 8pt ${_monospace}
hints = bold 13px ${_monospace}
debug-console = 8pt ${_monospace}
web-family-standard =
web-family-fixed =
web-family-serif =
web-family-sans-serif =
web-family-cursive =
web-family-fantasy =
web-size-minimum = 0
web-size-minimum-logical = 6
web-size-default = 16
web-size-default-fixed = 13
keyhint = 8pt ${_monospace}
messages.error = 8pt ${_monospace}
messages.warning = 8pt ${_monospace}
messages.info = 8pt ${_monospace}
prompts = 8pt sans-serif
"""

OLD_KEYS_CONF = """
[!normal]
leave-mode
    <escape>
    <ctrl-[>
[normal]
clear-keychain ;; search ;; fullscreen --leave
    <escape>
    <ctrl-[>
set-cmd-text -s :open
    o
set-cmd-text :open {url:pretty}
    go
set-cmd-text -s :open -t
    O
set-cmd-text :open -t -i {url:pretty}
    gO
set-cmd-text -s :open -b
    xo
set-cmd-text :open -b -i {url:pretty}
    xO
set-cmd-text -s :open -w
    wo
set-cmd-text :open -w {url:pretty}
    wO
set-cmd-text /
    /
set-cmd-text ?
    ?
set-cmd-text :
    :
open -t
    ga
    <ctrl-t>
open -w
    <ctrl-n>
tab-close
    d
    <ctrl-w>
tab-close -o
    D
tab-only
    co
tab-focus
    T
tab-move
    gm
tab-move -
    gl
tab-move +
    gr
tab-next
    J
    <ctrl-pgdown>
tab-prev
    K
    <ctrl-pgup>
tab-clone
    gC
reload
    r
    <f5>
reload -f
    R
    <ctrl-f5>
back
    H
    <back>
back -t
    th
back -w
    wh
forward
    L
    <forward>
forward -t
    tl
forward -w
    wl
fullscreen
    <f11>
hint
    f
hint all tab
    F
hint all window
    wf
hint all tab-bg
    ;b
hint all tab-fg
    ;f
hint all hover
    ;h
hint images
    ;i
hint images tab
    ;I
hint links fill :open {hint-url}
    ;o
hint links fill :open -t -i {hint-url}
    ;O
hint links yank
    ;y
hint links yank-primary
    ;Y
hint --rapid links tab-bg
    ;r
hint --rapid links window
    ;R
hint links download
    ;d
hint inputs
    ;t
scroll left
    h
scroll down
    j
scroll up
    k
scroll right
    l
undo
    u
    <ctrl-shift-t>
scroll-perc 0
    gg
scroll-perc
    G
search-next
    n
search-prev
    N
enter-mode insert
    i
enter-mode caret
    v
enter-mode set_mark
    `
enter-mode jump_mark
    '
yank
    yy
yank -s
    yY
yank title
    yt
yank title -s
    yT
yank domain
    yd
yank domain -s
    yD
yank pretty-url
    yp
yank pretty-url -s
    yP
open -- {clipboard}
    pp
open -- {primary}
    pP
open -t -- {clipboard}
    Pp
open -t -- {primary}
    PP
open -w -- {clipboard}
    wp
open -w -- {primary}
    wP
quickmark-save
    m
set-cmd-text -s :quickmark-load
    b
set-cmd-text -s :quickmark-load -t
    B
set-cmd-text -s :quickmark-load -w
    wb
bookmark-add
    M
set-cmd-text -s :bookmark-load
    gb
set-cmd-text -s :bookmark-load -t
    gB
set-cmd-text -s :bookmark-load -w
    wB
save
    sf
set-cmd-text -s :set
    ss
set-cmd-text -s :set -t
    sl
set-cmd-text -s :bind
    sk
zoom-out
    -
zoom-in
    +
zoom
    =
navigate prev
    [[
navigate next
    ]]
navigate prev -t
    {{
navigate next -t
    }}
navigate up
    gu
navigate up -t
    gU
navigate increment
    <ctrl-a>
navigate decrement
    <ctrl-x>
inspector
    wi
download
    gd
download-cancel
    ad
download-clear
    cd
view-source
    gf
set-cmd-text -s :buffer
    gt
tab-focus last
    <ctrl-tab>
    <ctrl-6>
    <ctrl-^>
enter-mode passthrough
    <ctrl-v>
quit
    <ctrl-q>
    ZQ
wq
    ZZ
scroll-page 0 1
    <ctrl-f>
scroll-page 0 -1
    <ctrl-b>
scroll-page 0 0.5
    <ctrl-d>
scroll-page 0 -0.5
    <ctrl-u>
tab-focus 1
    <alt-1>
    g0
    g^
tab-focus 2
    <alt-2>
tab-focus 3
    <alt-3>
tab-focus 4
    <alt-4>
tab-focus 5
    <alt-5>
tab-focus 6
    <alt-6>
tab-focus 7
    <alt-7>
tab-focus 8
    <alt-8>
tab-focus -1
    <alt-9>
    g$
home
    <ctrl-h>
stop
    <ctrl-s>
print
    <ctrl-alt-p>
open qute://settings
    Ss
follow-selected
    <return>
    <ctrl-m>
    <ctrl-j>
    <shift-return>
    <enter>
    <shift-enter>
follow-selected -t
    <ctrl-return>
    <ctrl-enter>
repeat-command
    .
tab-pin
    <ctrl-p>
record-macro
    q
run-macro
    @
[insert]
open-editor
    <ctrl-e>
insert-text {primary}
    <shift-ins>
[hint]
follow-hint
    <return>
    <ctrl-m>
    <ctrl-j>
    <shift-return>
    <enter>
    <shift-enter>
hint --rapid links tab-bg
    <ctrl-r>
hint links
    <ctrl-f>
hint all tab-bg
    <ctrl-b>
[passthrough]
[command]
command-history-prev
    <ctrl-p>
command-history-next
    <ctrl-n>
completion-item-focus prev
    <shift-tab>
    <up>
completion-item-focus next
    <tab>
    <down>
completion-item-focus next-category
    <ctrl-tab>
completion-item-focus prev-category
    <ctrl-shift-tab>
completion-item-del
    <ctrl-d>
command-accept
    <return>
    <ctrl-m>
    <ctrl-j>
    <shift-return>
    <enter>
    <shift-enter>
[prompt]
prompt-accept
    <return>
    <ctrl-m>
    <ctrl-j>
    <shift-return>
    <enter>
    <shift-enter>
prompt-accept yes
    y
prompt-accept no
    n
prompt-open-download
    <ctrl-x>
prompt-item-focus prev
    <shift-tab>
    <up>
prompt-item-focus next
    <tab>
    <down>
[command,prompt]
rl-backward-char
    <ctrl-b>
rl-forward-char
    <ctrl-f>
rl-backward-word
    <alt-b>
rl-forward-word
    <alt-f>
rl-beginning-of-line
    <ctrl-a>
rl-end-of-line
    <ctrl-e>
rl-unix-line-discard
    <ctrl-u>
rl-kill-line
    <ctrl-k>
rl-kill-word
    <alt-d>
rl-unix-word-rubout
    <ctrl-w>
rl-backward-kill-word
    <alt-backspace>
rl-yank
    <ctrl-y>
rl-delete-char
    <ctrl-?>
rl-backward-delete-char
    <ctrl-h>
[caret]
toggle-selection
    v
    <space>
drop-selection
    <ctrl-space>
enter-mode normal
    c
move-to-next-line
    j
move-to-prev-line
    k
move-to-next-char
    l
move-to-prev-char
    h
move-to-end-of-word
    e
move-to-next-word
    w
move-to-prev-word
    b
move-to-start-of-next-block
    ]
move-to-start-of-prev-block
    [
move-to-end-of-next-block
    }
move-to-end-of-prev-block
    {
move-to-start-of-line
    0
move-to-end-of-line
    $
move-to-start-of-document
    gg
move-to-end-of-document
    G
yank selection -s
    Y
yank selection
    y
    <return>
    <ctrl-m>
    <ctrl-j>
    <shift-return>
    <enter>
    <shift-enter>
scroll left
    H
scroll down
    J
scroll up
    K
scroll right
    L
"""


def get_diff() -> str:
    """Get a HTML diff for the old config files."""
    old_conf_lines = []  # type: typing.MutableSequence[str]
    old_key_lines = []  # type: typing.MutableSequence[str]

    for filename, dest in [('qutebrowser.conf', old_conf_lines),
                           ('keys.conf', old_key_lines)]:
        path = os.path.join(standarddir.config(), filename)

        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip() or line.startswith('#'):
                    continue
                dest.append(line.rstrip())

    conf_delta = difflib.unified_diff(OLD_CONF.lstrip().splitlines(),
                                      old_conf_lines)
    key_delta = difflib.unified_diff(OLD_KEYS_CONF.lstrip().splitlines(),
                                     old_key_lines)

    conf_diff = '\n'.join(conf_delta)
    key_diff = '\n'.join(key_delta)

    # pylint: disable=no-member
    # WORKAROUND for https://bitbucket.org/logilab/pylint/issue/491/
    lexer = pygments.lexers.DiffLexer()
    formatter = pygments.formatters.HtmlFormatter(
        full=True, linenos='table',
        title='Diffing pre-1.0 default config with pre-1.0 modified config')
    # pylint: enable=no-member
    return pygments.highlight(conf_diff + key_diff, lexer, formatter)
