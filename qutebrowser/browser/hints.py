# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""A HintManager to draw hints over links."""

import collections
import functools
import math
import re
from string import ascii_lowercase

from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QObject, QEvent, Qt, QUrl,
                          QTimer)
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWebKit import QWebElement
from PyQt5.QtWebKitWidgets import QWebPage

from qutebrowser.config import config
from qutebrowser.keyinput import modeman, modeparsers
from qutebrowser.browser.webkit import webelem
from qutebrowser.commands import userscripts, cmdexc, cmdutils, runners
from qutebrowser.utils import usertypes, log, qtutils, message, objreg, utils


ElemTuple = collections.namedtuple('ElemTuple', ['elem', 'label'])


Target = usertypes.enum('Target', ['normal', 'current', 'tab', 'tab_fg',
                                   'tab_bg', 'window', 'yank', 'yank_primary',
                                   'run', 'fill', 'hover', 'download',
                                   'userscript', 'spawn'])


class WordHintingError(Exception):

    """Exception raised on errors during word hinting."""


def on_mode_entered(mode, win_id):
    """Stop hinting when insert mode was entered."""
    if mode == usertypes.KeyMode.insert:
        modeman.maybe_leave(win_id, usertypes.KeyMode.hint, 'insert mode')


class HintContext:

    """Context namespace used for hinting.

    Attributes:
        frames: The QWebFrames to use.
        all_elems: A list of all (elem, label) namedtuples ever created.
        elems: A mapping from key strings to (elem, label) namedtuples.
               May contain less elements than `all_elems` due to filtering.
        baseurl: The URL of the current page.
        target: What to do with the opened links.
                normal/current/tab/tab_fg/tab_bg/window: Get passed to
                                                         BrowserTab.
                yank/yank_primary: Yank to clipboard/primary selection.
                run: Run a command.
                fill: Fill commandline with link.
                download: Download the link.
                userscript: Call a custom userscript.
                spawn: Spawn a simple command.
        to_follow: The link to follow when enter is pressed.
        args: Custom arguments for userscript/spawn
        rapid: Whether to do rapid hinting.
        tab: The WebTab object we started hinting in.
        group: The group of web elements to hint.
    """

    def __init__(self):
        self.all_elems = []
        self.elems = {}
        self.target = None
        self.baseurl = None
        self.to_follow = None
        self.rapid = False
        self.frames = []
        self.args = []
        self.tab = None
        self.group = None

    def get_args(self, urlstr):
        """Get the arguments, with {hint-url} replaced by the given URL."""
        args = []
        for arg in self.args:
            arg = arg.replace('{hint-url}', urlstr)
            args.append(arg)
        return args


class HintManager(QObject):

    """Manage drawing hints over links or other elements.

    Class attributes:
        HINT_TEXTS: Text displayed for different hinting modes.

    Attributes:
        _context: The HintContext for the current invocation.
        _win_id: The window ID this HintManager is associated with.
        _tab_id: The tab ID this HintManager is associated with.
        _filterstr: Used to save the filter string for restoring in rapid mode.

    Signals:
        mouse_event: Mouse event to be posted in the web view.
                     arg: A QMouseEvent
        start_hinting: Emitted when hinting starts, before a link is clicked.
                       arg: The ClickTarget to use.
        stop_hinting: Emitted after a link was clicked.
    """

    HINT_TEXTS = {
        Target.normal: "Follow hint",
        Target.current: "Follow hint in current tab",
        Target.tab: "Follow hint in new tab",
        Target.tab_fg: "Follow hint in foreground tab",
        Target.tab_bg: "Follow hint in background tab",
        Target.window: "Follow hint in new window",
        Target.yank: "Yank hint to clipboard",
        Target.yank_primary: "Yank hint to primary selection",
        Target.run: "Run a command on a hint",
        Target.fill: "Set hint in commandline",
        Target.hover: "Hover over a hint",
        Target.download: "Download hint",
        Target.userscript: "Call userscript via hint",
        Target.spawn: "Spawn command via hint",
    }

    mouse_event = pyqtSignal('QMouseEvent')
    start_hinting = pyqtSignal(usertypes.ClickTarget)
    stop_hinting = pyqtSignal()

    def __init__(self, win_id, tab_id, parent=None):
        """Constructor."""
        super().__init__(parent)
        self._win_id = win_id
        self._tab_id = tab_id
        self._context = None
        self._filterstr = None
        self._word_hinter = WordHinter()
        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=win_id)
        mode_manager.left.connect(self.on_mode_left)

    def _get_text(self):
        """Get a hint text based on the current context."""
        text = self.HINT_TEXTS[self._context.target]
        if self._context.rapid:
            text += ' (rapid mode)'
        text += '...'
        return text

    def _cleanup(self):
        """Clean up after hinting."""
        for elem in self._context.all_elems:
            try:
                elem.label.remove_from_document()
            except webelem.IsNullError:
                pass
        text = self._get_text()
        message_bridge = objreg.get('message-bridge', scope='window',
                                    window=self._win_id)
        message_bridge.maybe_reset_text(text)
        self._context = None
        self._filterstr = None

    def _hint_strings(self, elems):
        """Calculate the hint strings for elems.

        Inspired by Vimium.

        Args:
            elems: The elements to get hint strings for.

        Return:
            A list of hint strings, in the same order as the elements.
        """
        hint_mode = config.get('hints', 'mode')
        if hint_mode == 'word':
            try:
                return self._word_hinter.hint(elems)
            except WordHintingError as e:
                message.error(self._win_id, str(e), immediately=True)
                # falls back on letter hints
        if hint_mode == 'number':
            chars = '0123456789'
        else:
            chars = config.get('hints', 'chars')
        min_chars = config.get('hints', 'min-chars')
        if config.get('hints', 'scatter') and hint_mode != 'number':
            return self._hint_scattered(min_chars, chars, elems)
        else:
            return self._hint_linear(min_chars, chars, elems)

    def _hint_scattered(self, min_chars, chars, elems):
        """Produce scattered hint labels with variable length (like Vimium).

        Args:
            min_chars: The minimum length of labels.
            chars: The alphabet to use for labels.
            elems: The elements to generate labels for.
        """
        # Determine how many digits the link hints will require in the worst
        # case. Usually we do not need all of these digits for every link
        # single hint, so we can show shorter hints for a few of the links.
        needed = max(min_chars, math.ceil(math.log(len(elems), len(chars))))
        # Short hints are the number of hints we can possibly show which are
        # (needed - 1) digits in length.
        if needed > min_chars:
            short_count = math.floor((len(chars) ** needed - len(elems)) /
                                     len(chars))
        else:
            short_count = 0

        long_count = len(elems) - short_count

        strings = []

        if needed > 1:
            for i in range(short_count):
                strings.append(self._number_to_hint_str(i, chars, needed - 1))

        start = short_count * len(chars)
        for i in range(start, start + long_count):
            strings.append(self._number_to_hint_str(i, chars, needed))

        return self._shuffle_hints(strings, len(chars))

    def _hint_linear(self, min_chars, chars, elems):
        """Produce linear hint labels with constant length (like dwb).

        Args:
            min_chars: The minimum length of labels.
            chars: The alphabet to use for labels.
            elems: The elements to generate labels for.
        """
        strings = []
        needed = max(min_chars, math.ceil(math.log(len(elems), len(chars))))
        for i in range(len(elems)):
            strings.append(self._number_to_hint_str(i, chars, needed))
        return strings

    def _shuffle_hints(self, hints, length):
        """Shuffle the given set of hints so that they're scattered.

        Hints starting with the same character will be spread evenly throughout
        the array.

        Inspired by Vimium.

        Args:
            hints: A list of hint strings.
            length: Length of the available charset.

        Return:
            A list of shuffled hint strings.
        """
        buckets = [[] for i in range(length)]
        for i, hint in enumerate(hints):
            buckets[i % len(buckets)].append(hint)
        result = []
        for bucket in buckets:
            result += bucket
        return result

    def _number_to_hint_str(self, number, chars, digits=0):
        """Convert a number like "8" into a hint string like "JK".

        This is used to sequentially generate all of the hint text.
        The hint string will be "padded with zeroes" to ensure its length is >=
        digits.

        Inspired by Vimium.

        Args:
            number: The hint number.
            chars: The charset to use.
            digits: The minimum output length.

        Return:
            A hint string.
        """
        base = len(chars)
        hintstr = []
        remainder = 0
        while True:
            remainder = number % base
            hintstr.insert(0, chars[remainder])
            number -= remainder
            number //= base
            if number <= 0:
                break
        # Pad the hint string we're returning so that it matches digits.
        for _ in range(0, digits - len(hintstr)):
            hintstr.insert(0, chars[0])
        return ''.join(hintstr)

    def _is_hidden(self, elem):
        """Check if the element is hidden via display=none."""
        display = elem.style_property('display', QWebElement.InlineStyle)
        return display == 'none'

    def _show_elem(self, elem):
        """Show a given element."""
        elem.set_style_property('display', 'inline !important')

    def _hide_elem(self, elem):
        """Hide a given element."""
        elem.set_style_property('display', 'none !important')

    def _set_style_properties(self, elem, label):
        """Set the hint CSS on the element given.

        Args:
            elem: The QWebElement to set the style attributes for.
            label: The label QWebElement.
        """
        attrs = [
            ('display', 'inline !important'),
            ('z-index', '{} !important'.format(int(2 ** 32 / 2 - 1))),
            ('pointer-events', 'none !important'),
            ('position', 'fixed !important'),
            ('color', config.get('colors', 'hints.fg') + ' !important'),
            ('background', config.get('colors', 'hints.bg') + ' !important'),
            ('font', config.get('fonts', 'hints') + ' !important'),
            ('border', config.get('hints', 'border') + ' !important'),
            ('opacity', str(config.get('hints', 'opacity')) + ' !important'),
        ]

        # Make text uppercase if set in config
        if (config.get('hints', 'uppercase') and
                config.get('hints', 'mode') == 'letter'):
            attrs.append(('text-transform', 'uppercase !important'))
        else:
            attrs.append(('text-transform', 'none !important'))

        for k, v in attrs:
            label.set_style_property(k, v)
        self._set_style_position(elem, label)

    def _set_style_position(self, elem, label):
        """Set the CSS position of the label element.

        Args:
            elem: The QWebElement to set the style attributes for.
            label: The label QWebElement.
        """
        no_js = config.get('hints', 'find-implementation') != 'javascript'
        rect = elem.rect_on_view(adjust_zoom=False, no_js=no_js)
        left = rect.x()
        top = rect.y()
        log.hints.vdebug("Drawing label '{!r}' at {}/{} for element '{!r}' "
                         "(no_js: {})".format(label, left, top, elem, no_js))
        label.set_style_property('left', '{}px !important'.format(left))
        label.set_style_property('top', '{}px !important'.format(top))

    def _draw_label(self, elem, string):
        """Draw a hint label over an element.

        Args:
            elem: The QWebElement to use.
            string: The hint string to print.

        Return:
            The newly created label element
        """
        doc = elem.document_element()
        body = doc.find_first('body')
        if body is None:
            parent = doc
        else:
            parent = body
        label = parent.create_inside('span')
        label['class'] = 'qutehint'
        self._set_style_properties(elem, label)
        label.set_text(string)
        return label

    def _show_url_error(self):
        """Show an error because no link was found."""
        message.error(self._win_id, "No suitable link found for this element.",
                      immediately=True)

    def _click(self, elem, context):
        """Click an element.

        Args:
            elem: The QWebElement to click.
            context: The HintContext to use.
        """
        target_mapping = {
            Target.normal: usertypes.ClickTarget.normal,
            Target.current: usertypes.ClickTarget.normal,
            Target.tab_fg: usertypes.ClickTarget.tab,
            Target.tab_bg: usertypes.ClickTarget.tab_bg,
            Target.window: usertypes.ClickTarget.window,
            Target.hover: usertypes.ClickTarget.normal,
        }
        if config.get('tabs', 'background-tabs'):
            target_mapping[Target.tab] = usertypes.ClickTarget.tab_bg
        else:
            target_mapping[Target.tab] = usertypes.ClickTarget.tab

        # Click the center of the largest square fitting into the top/left
        # corner of the rectangle, this will help if part of the <a> element
        # is hidden behind other elements
        # https://github.com/The-Compiler/qutebrowser/issues/1005
        rect = elem.rect_on_view()
        if rect.width() > rect.height():
            rect.setWidth(rect.height())
        else:
            rect.setHeight(rect.width())
        pos = rect.center()

        action = "Hovering" if context.target == Target.hover else "Clicking"
        log.hints.debug("{} on '{}' at position {}".format(
            action, elem.debug_text(), pos))

        self.start_hinting.emit(target_mapping[context.target])
        if context.target in [Target.tab, Target.tab_fg, Target.tab_bg,
                              Target.window]:
            modifiers = Qt.ControlModifier
        else:
            modifiers = Qt.NoModifier
        events = [
            QMouseEvent(QEvent.MouseMove, pos, Qt.NoButton, Qt.NoButton,
                        Qt.NoModifier),
        ]
        if context.target != Target.hover:
            events += [
                QMouseEvent(QEvent.MouseButtonPress, pos, Qt.LeftButton,
                            Qt.LeftButton, modifiers),
                QMouseEvent(QEvent.MouseButtonRelease, pos, Qt.LeftButton,
                            Qt.NoButton, modifiers),
            ]

        if context.target in [Target.normal, Target.current]:
            # Set the pre-jump mark ', so we can jump back here after following
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=self._win_id)
            tabbed_browser.set_mark("'")

        if context.target == Target.current:
            elem.remove_blank_target()
        for evt in events:
            self.mouse_event.emit(evt)
        if elem.is_text_input() and elem.is_editable():
            QTimer.singleShot(0, functools.partial(
                elem.frame().page().triggerAction,
                QWebPage.MoveToEndOfDocument))
        QTimer.singleShot(0, self.stop_hinting.emit)

    def _yank(self, url, context):
        """Yank an element to the clipboard or primary selection.

        Args:
            url: The URL to open as a QUrl.
            context: The HintContext to use.
        """
        sel = (context.target == Target.yank_primary and
               utils.supports_selection())

        urlstr = url.toString(QUrl.FullyEncoded | QUrl.RemovePassword)
        utils.set_clipboard(urlstr, selection=sel)

        msg = "Yanked URL to {}: {}".format(
            "primary selection" if sel else "clipboard",
            urlstr)
        message.info(self._win_id, msg)

    def _run_cmd(self, url, context):
        """Run the command based on a hint URL.

        Args:
            url: The URL to open as a QUrl.
            context: The HintContext to use.
        """
        urlstr = url.toString(QUrl.FullyEncoded)
        args = context.get_args(urlstr)
        commandrunner = runners.CommandRunner(self._win_id)
        commandrunner.run_safely(' '.join(args))

    def _preset_cmd_text(self, url, context):
        """Preset a commandline text based on a hint URL.

        Args:
            url: The URL to open as a QUrl.
            context: The HintContext to use.
        """
        urlstr = url.toDisplayString(QUrl.FullyEncoded)
        args = context.get_args(urlstr)
        text = ' '.join(args)
        if text[0] not in modeparsers.STARTCHARS:
            message.error(self._win_id,
                          "Invalid command text '{}'.".format(text),
                          immediately=True)
        else:
            message.set_cmd_text(self._win_id, text)

    def _download(self, elem, context):
        """Download a hint URL.

        Args:
            elem: The QWebElement to download.
            _context: The HintContext to use.
        """
        url = self._resolve_url(elem, context.baseurl)
        if url is None:
            self._show_url_error()
            return
        if context.rapid:
            prompt = False
        else:
            prompt = None

        download_manager = objreg.get('download-manager', scope='window',
                                      window=self._win_id)
        download_manager.get(url, page=elem.frame().page(),
                             prompt_download_directory=prompt)

    def _call_userscript(self, elem, context):
        """Call a userscript from a hint.

        Args:
            elem: The QWebElement to use in the userscript.
            context: The HintContext to use.
        """
        cmd = context.args[0]
        args = context.args[1:]
        env = {
            'QUTE_MODE': 'hints',
            'QUTE_SELECTED_TEXT': str(elem),
            'QUTE_SELECTED_HTML': elem.outer_xml(),
        }
        url = self._resolve_url(elem, context.baseurl)
        if url is not None:
            env['QUTE_URL'] = url.toString(QUrl.FullyEncoded)

        try:
            userscripts.run_async(context.tab, cmd, *args, win_id=self._win_id,
                                  env=env)
        except userscripts.UnsupportedError as e:
            message.error(self._win_id, str(e), immediately=True)

    def _spawn(self, url, context):
        """Spawn a simple command from a hint.

        Args:
            url: The URL to open as a QUrl.
            context: The HintContext to use.
        """
        urlstr = url.toString(QUrl.FullyEncoded | QUrl.RemovePassword)
        args = context.get_args(urlstr)
        commandrunner = runners.CommandRunner(self._win_id)
        commandrunner.run_safely('spawn ' + ' '.join(args))

    def _resolve_url(self, elem, baseurl):
        """Resolve a URL and check if we want to keep it.

        Args:
            elem: The QWebElement to get the URL of.
            baseurl: The baseurl of the current tab.

        Return:
            A QUrl with the absolute URL, or None.
        """
        for attr in ['href', 'src']:
            if attr in elem:
                text = elem[attr].strip()
                break
        else:
            return None

        url = QUrl(text)
        if not url.isValid():
            return None
        if url.isRelative():
            url = baseurl.resolved(url)
        qtutils.ensure_valid(url)
        return url

    def _find_prevnext(self, tab, prev=False):
        """Find a prev/next element in frame."""
        # First check for <link rel="prev(ious)|next">
        elems = tab.find_all_elements(webelem.SELECTORS[webelem.Group.links])
        rel_values = ('prev', 'previous') if prev else ('next')
        for e in elems:
            try:
                rel_attr = e['rel']
            except KeyError:
                continue
            if rel_attr in rel_values:
                log.hints.debug("Found '{}' with rel={}".format(
                    e.debug_text(), rel_attr))
                return e
        # Then check for regular links/buttons.
        elems = tab.find_all_elements(
            webelem.SELECTORS[webelem.Group.prevnext])
        filterfunc = webelem.FILTERS[webelem.Group.prevnext]
        elems = [e for e in elems if filterfunc(e)]

        option = 'prev-regexes' if prev else 'next-regexes'
        if not elems:
            return None
        for regex in config.get('hints', option):
            log.hints.vdebug("== Checking regex '{}'.".format(regex.pattern))
            for e in elems:
                text = str(e)
                if not text:
                    continue
                if regex.search(text):
                    log.hints.debug("Regex '{}' matched on '{}'.".format(
                        regex.pattern, text))
                    return e
                else:
                    log.hints.vdebug("No match on '{}'!".format(text))
        return None

    def _check_args(self, target, *args):
        """Check the arguments passed to start() and raise if they're wrong.

        Args:
            target: A Target enum member.
            args: Arguments for userscript/download
        """
        if not isinstance(target, Target):
            raise TypeError("Target {} is no Target member!".format(target))
        if target in [Target.userscript, Target.spawn, Target.run,
                      Target.fill]:
            if not args:
                raise cmdexc.CommandError(
                    "'args' is required with target userscript/spawn/run/"
                    "fill.")
        else:
            if args:
                raise cmdexc.CommandError(
                    "'args' is only allowed with target userscript/spawn.")

    def _init_elements(self):
        """Initialize the elements and labels based on the context set."""
        selector = webelem.SELECTORS[self._context.group]
        elems = self._context.tab.find_all_elements(selector)
        elems = [e for e in elems if e.is_visible()]
        filterfunc = webelem.FILTERS.get(self._context.group, lambda e: True)
        elems = [e for e in elems if filterfunc(e)]
        if not elems:
            raise cmdexc.CommandError("No elements found.")
        strings = self._hint_strings(elems)
        log.hints.debug("hints: {}".format(', '.join(strings)))
        for e, string in zip(elems, strings):
            label = self._draw_label(e, string)
            elem = ElemTuple(e, label)
            self._context.all_elems.append(elem)
            self._context.elems[string] = elem
        keyparsers = objreg.get('keyparsers', scope='window',
                                window=self._win_id)
        keyparser = keyparsers[usertypes.KeyMode.hint]
        keyparser.update_bindings(strings)

    def _filter_matches(self, filterstr, elemstr):
        """Return True if `filterstr` matches `elemstr`."""
        # Empty string and None always match
        if not filterstr:
            return True
        filterstr = filterstr.casefold()
        elemstr = elemstr.casefold()
        # Do multi-word matching
        return all(word in elemstr for word in filterstr.split())

    def follow_prevnext(self, browsertab, baseurl, prev=False, tab=False,
                        background=False, window=False):
        """Click a "previous"/"next" element on the page.

        Args:
            browsertab: The WebKitTab/WebEngineTab of the page.
            baseurl: The base URL of the current tab.
            prev: True to open a "previous" link, False to open a "next" link.
            tab: True to open in a new tab, False for the current tab.
            background: True to open in a background tab.
            window: True to open in a new window, False for the current one.
        """
        from qutebrowser.mainwindow import mainwindow
        elem = self._find_prevnext(browsertab, prev)
        if elem is None:
            raise cmdexc.CommandError("No {} links found!".format(
                "prev" if prev else "forward"))
        url = self._resolve_url(elem, baseurl)
        if url is None:
            raise cmdexc.CommandError("No {} links found!".format(
                "prev" if prev else "forward"))
        qtutils.ensure_valid(url)
        if window:
            new_window = mainwindow.MainWindow()
            new_window.show()
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=new_window.win_id)
            tabbed_browser.tabopen(url, background=False)
        elif tab:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=self._win_id)
            tabbed_browser.tabopen(url, background=background)
        else:
            tab = objreg.get('tab', scope='tab', window=self._win_id,
                             tab=self._tab_id)
            tab.openurl(url)

    @cmdutils.register(instance='hintmanager', scope='tab', name='hint',
                       star_args_optional=True, maxsplit=2,
                       backend=usertypes.Backend.QtWebKit)
    @cmdutils.argument('win_id', win_id=True)
    def start(self, rapid=False, group=webelem.Group.all, target=Target.normal,
              *args, win_id):
        """Start hinting.

        Args:
            rapid: Whether to do rapid hinting. This is only possible with
                   targets `tab` (with background-tabs=true), `tab-bg`,
                   `window`, `run`, `hover`, `userscript` and `spawn`.
            group: The hinting mode to use.

                - `all`: All clickable elements.
                - `links`: Only links.
                - `images`: Only images.
                - `inputs`: Only input fields.

            target: What to do with the selected element.

                - `normal`: Open the link.
                - `current`: Open the link in the current tab.
                - `tab`: Open the link in a new tab (honoring the
                         background-tabs setting).
                - `tab-fg`: Open the link in a new foreground tab.
                - `tab-bg`: Open the link in a new background tab.
                - `window`: Open the link in a new window.
                - `hover` : Hover over the link.
                - `yank`: Yank the link to the clipboard.
                - `yank-primary`: Yank the link to the primary selection.
                - `run`: Run the argument as command.
                - `fill`: Fill the commandline with the command given as
                          argument.
                - `download`: Download the link.
                - `userscript`: Call a userscript with `$QUTE_URL` set to the
                                link.
                - `spawn`: Spawn a command.

            *args: Arguments for spawn/userscript/run/fill.

                - With `spawn`: The executable and arguments to spawn.
                                `{hint-url}` will get replaced by the selected
                                URL.
                - With `userscript`: The userscript to execute. Either store
                                     the userscript in
                                     `~/.local/share/qutebrowser/userscripts`
                                     (or `$XDG_DATA_DIR`), or use an absolute
                                     path.
                - With `fill`: The command to fill the statusbar with.
                                `{hint-url}` will get replaced by the selected
                                URL.
                - With `run`: Same as `fill`.
        """
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        tab = tabbed_browser.currentWidget()
        if tab is None:
            raise cmdexc.CommandError("No WebView available yet!")
        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=self._win_id)
        if mode_manager.mode == usertypes.KeyMode.hint:
            modeman.leave(win_id, usertypes.KeyMode.hint, 're-hinting')

        if rapid:
            if target in [Target.tab_bg, Target.window, Target.run,
                          Target.hover, Target.userscript, Target.spawn,
                          Target.download, Target.normal, Target.current]:
                pass
            elif (target == Target.tab and
                  config.get('tabs', 'background-tabs')):
                pass
            else:
                name = target.name.replace('_', '-')
                raise cmdexc.CommandError("Rapid hinting makes no sense with "
                                          "target {}!".format(name))

        self._check_args(target, *args)
        self._context = HintContext()
        self._context.tab = tab
        self._context.target = target
        self._context.rapid = rapid
        try:
            self._context.baseurl = tabbed_browser.current_url()
        except qtutils.QtValueError:
            raise cmdexc.CommandError("No URL set for this page yet!")
        self._context.tab = tab
        self._context.args = args
        self._context.group = group
        self._init_elements()
        message_bridge = objreg.get('message-bridge', scope='window',
                                    window=self._win_id)
        message_bridge.set_text(self._get_text())
        modeman.enter(self._win_id, usertypes.KeyMode.hint,
                      'HintManager.start')

    def handle_partial_key(self, keystr):
        """Handle a new partial keypress."""
        log.hints.debug("Handling new keystring: '{}'".format(keystr))
        for string, elem in self._context.elems.items():
            try:
                if string.startswith(keystr):
                    matched = string[:len(keystr)]
                    rest = string[len(keystr):]
                    match_color = config.get('colors', 'hints.fg.match')
                    elem.label.set_inner_xml(
                        '<font color="{}">{}</font>{}'.format(
                            match_color, matched, rest))
                    if self._is_hidden(elem.label):
                        # hidden element which matches again -> show it
                        self._show_elem(elem.label)
                else:
                    # element doesn't match anymore -> hide it
                    self._hide_elem(elem.label)
            except webelem.IsNullError:
                pass

    def _filter_number_hints(self):
        """Apply filters for numbered hints and renumber them.

        Return:
            Elements which are still visible
        """
        # renumber filtered hints
        elems = []
        for e in self._context.all_elems:
            try:
                if not self._is_hidden(e.label):
                    elems.append(e)
            except webelem.IsNullError:
                pass
        if not elems:
            # Whoops, filtered all hints
            modeman.leave(self._win_id, usertypes.KeyMode.hint,
                          'all filtered')
            return {}

        strings = self._hint_strings(elems)
        self._context.elems = {}
        for elem, string in zip(elems, strings):
            elem.label.set_inner_xml(string)
            self._context.elems[string] = elem
        keyparsers = objreg.get('keyparsers', scope='window',
                                window=self._win_id)
        keyparser = keyparsers[usertypes.KeyMode.hint]
        keyparser.update_bindings(strings, preserve_filter=True)

        return self._context.elems

    def _filter_non_number_hints(self):
        """Apply filters for letter/word hints.

        Return:
            Elements which are still visible
        """
        visible = {}
        for string, elem in self._context.elems.items():
            try:
                if not self._is_hidden(elem.label):
                    visible[string] = elem
            except webelem.IsNullError:
                pass
        if not visible:
            # Whoops, filtered all hints
            modeman.leave(self._win_id, usertypes.KeyMode.hint,
                          'all filtered')
        return visible

    def filter_hints(self, filterstr):
        """Filter displayed hints according to a text.

        Args:
            filterstr: The string to filter with, or None to use the filter
                       from previous call (saved in `self._filterstr`). If
                       `filterstr` is an empty string or if both `filterstr`
                       and `self._filterstr` are None, all hints are shown.
        """
        if filterstr is None:
            filterstr = self._filterstr
        else:
            self._filterstr = filterstr

        for elem in self._context.all_elems:
            try:
                if self._filter_matches(filterstr, str(elem.elem)):
                    if self._is_hidden(elem.label):
                        # hidden element which matches again -> show it
                        self._show_elem(elem.label)
                else:
                    # element doesn't match anymore -> hide it
                    self._hide_elem(elem.label)
            except webelem.IsNullError:
                pass

        if config.get('hints', 'mode') == 'number':
            visible = self._filter_number_hints()
        else:
            visible = self._filter_non_number_hints()

        if (len(visible) == 1 and
                config.get('hints', 'auto-follow') and
                filterstr is not None):
            # apply auto-follow-timeout
            timeout = config.get('hints', 'auto-follow-timeout')
            keyparsers = objreg.get('keyparsers', scope='window',
                                    window=self._win_id)
            normal_parser = keyparsers[usertypes.KeyMode.normal]
            normal_parser.set_inhibited_timeout(timeout)
            # unpacking gets us the first (and only) key in the dict.
            self.fire(*visible)

    def fire(self, keystr, force=False):
        """Fire a completed hint.

        Args:
            keystr: The keychain string to follow.
            force: When True, follow even when auto-follow is false.
        """
        if not (force or config.get('hints', 'auto-follow')):
            self.handle_partial_key(keystr)
            self._context.to_follow = keystr
            return
        # Handlers which take a QWebElement
        elem_handlers = {
            Target.normal: self._click,
            Target.current: self._click,
            Target.tab: self._click,
            Target.tab_fg: self._click,
            Target.tab_bg: self._click,
            Target.window: self._click,
            Target.hover: self._click,
            # _download needs a QWebElement to get the frame.
            Target.download: self._download,
            Target.userscript: self._call_userscript,
        }
        # Handlers which take a QUrl
        url_handlers = {
            Target.yank: self._yank,
            Target.yank_primary: self._yank,
            Target.run: self._run_cmd,
            Target.fill: self._preset_cmd_text,
            Target.spawn: self._spawn,
        }
        elem = self._context.elems[keystr].elem
        if elem.frame() is None:
            message.error(self._win_id,
                          "This element has no webframe.",
                          immediately=True)
            return
        if self._context.target in elem_handlers:
            handler = functools.partial(elem_handlers[self._context.target],
                                        elem, self._context)
        elif self._context.target in url_handlers:
            url = self._resolve_url(elem, self._context.baseurl)
            if url is None:
                self._show_url_error()
                return
            handler = functools.partial(url_handlers[self._context.target],
                                        url, self._context)
        else:
            raise ValueError("No suitable handler found!")
        if not self._context.rapid:
            modeman.maybe_leave(self._win_id, usertypes.KeyMode.hint,
                                'followed')
        else:
            # Reset filtering
            self.filter_hints(None)
            # Undo keystring highlighting
            for string, elem in self._context.elems.items():
                elem.label.set_inner_xml(string)
        handler()

    @cmdutils.register(instance='hintmanager', scope='tab', hide=True,
                       modes=[usertypes.KeyMode.hint])
    def follow_hint(self, keystring=None):
        """Follow a hint.

        Args:
            keystring: The hint to follow, or None.
        """
        if keystring is None:
            if self._context.to_follow is None:
                raise cmdexc.CommandError("No hint to follow")
            else:
                keystring = self._context.to_follow
        elif keystring not in self._context.elems:
            raise cmdexc.CommandError("No hint {}!".format(keystring))
        self.fire(keystring, force=True)

    @pyqtSlot('QSize')
    def on_contents_size_changed(self, _size):
        """Reposition hints if contents size changed."""
        log.hints.debug("Contents size changed...!")
        for e in self._context.all_elems:
            try:
                if e.elem.frame() is None:
                    # This sometimes happens for some reason...
                    e.label.remove_from_document()
                    continue
                self._set_style_position(e.elem, e.label)
            except webelem.IsNullError:
                pass

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Stop hinting when hinting mode was left."""
        if mode != usertypes.KeyMode.hint or self._context is None:
            # We have one HintManager per tab, so when this gets called,
            # self._context might be None, because the current tab is not
            # hinting.
            return
        self._cleanup()


class WordHinter:

    """Generator for word hints.

    Attributes:
        words: A set of words to be used when no "smart hint" can be
            derived from the hinted element.
    """

    def __init__(self):
        # will be initialized on first use.
        self.words = set()
        self.dictionary = None

    def ensure_initialized(self):
        """Generate the used words if yet uninitialized."""
        dictionary = config.get("hints", "dictionary")
        if not self.words or self.dictionary != dictionary:
            self.words.clear()
            self.dictionary = dictionary
            try:
                with open(dictionary, encoding="UTF-8") as wordfile:
                    alphabet = set(ascii_lowercase)
                    hints = set()
                    lines = (line.rstrip().lower() for line in wordfile)
                    for word in lines:
                        if set(word) - alphabet:
                            # contains none-alphabetic chars
                            continue
                        if len(word) > 4:
                            # we don't need words longer than 4
                            continue
                        for i in range(len(word)):
                            # remove all prefixes of this word
                            hints.discard(word[:i + 1])
                        hints.add(word)
                    self.words.update(hints)
            except IOError as e:
                error = "Word hints requires reading the file at {}: {}"
                raise WordHintingError(error.format(dictionary, str(e)))

    def extract_tag_words(self, elem):
        """Extract tag words form the given element."""
        attr_extractors = {
            "alt": lambda elem: elem["alt"],
            "name": lambda elem: elem["name"],
            "title": lambda elem: elem["title"],
            "src": lambda elem: elem["src"].split('/')[-1],
            "href": lambda elem: elem["href"].split('/')[-1],
            "text": str,
        }

        extractable_attrs = collections.defaultdict(list, {
            "IMG": ["alt", "title", "src"],
            "A": ["title", "href", "text"],
            "INPUT": ["name"]
        })

        return (attr_extractors[attr](elem)
                for attr in extractable_attrs[elem.tag_name()]
                if attr in elem or attr == "text")

    def tag_words_to_hints(self, words):
        """Take words and transform them to proper hints if possible."""
        for candidate in words:
            if not candidate:
                continue
            match = re.search('[A-Za-z]{3,}', candidate)
            if not match:
                continue
            if 4 < match.end() - match.start() < 8:
                yield candidate[match.start():match.end()].lower()

    def any_prefix(self, hint, existing):
        return any(hint.startswith(e) or e.startswith(hint) for e in existing)

    def filter_prefixes(self, hints, existing):
        return (h for h in hints if not self.any_prefix(h, existing))

    def new_hint_for(self, elem, existing, fallback):
        """Return a hint for elem, not conflicting with the existing."""
        new = self.tag_words_to_hints(self.extract_tag_words(elem))
        new_no_prefixes = self.filter_prefixes(new, existing)
        fallback_no_prefixes = self.filter_prefixes(fallback, existing)
        # either the first good, or None
        return (next(new_no_prefixes, None) or
                next(fallback_no_prefixes, None))

    def hint(self, elems):
        """Produce hint labels based on the html tags.

        Produce hint words based on the link text and random words
        from the words arg as fallback.

        Args:
            words: Words to use as fallback when no link text can be used.
            elems: The elements to get hint strings for.

        Return:
            A list of hint strings, in the same order as the elements.
        """
        self.ensure_initialized()
        hints = []
        used_hints = set()
        words = iter(self.words)
        for elem in elems:
            hint = self.new_hint_for(elem, used_hints, words)
            if not hint:
                raise WordHintingError("Not enough words in the dictionary.")
            used_hints.add(hint)
            hints.append(hint)
        return hints
