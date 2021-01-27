# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""A HintManager to draw hints over links."""

import collections
import functools
import os
import re
import html
import enum
import dataclasses
from string import ascii_lowercase
from typing import (TYPE_CHECKING, Callable, Dict, Iterable, Iterator, List, Mapping,
                    MutableSequence, Optional, Sequence, Set)

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, Qt, QUrl
from PyQt5.QtWidgets import QLabel

from qutebrowser.config import config, configexc
from qutebrowser.keyinput import modeman, modeparsers, basekeyparser
from qutebrowser.browser import webelem, history
from qutebrowser.commands import userscripts, runners
from qutebrowser.api import cmdutils
from qutebrowser.misc import overlap
from qutebrowser.utils import usertypes, log, qtutils, message, objreg, utils
if TYPE_CHECKING:
    from qutebrowser.browser import browsertab


class Target(enum.Enum):

    """What action to take on a hint."""

    normal = enum.auto()
    current = enum.auto()
    tab = enum.auto()
    tab_fg = enum.auto()
    tab_bg = enum.auto()
    window = enum.auto()
    yank = enum.auto()
    yank_primary = enum.auto()
    run = enum.auto()
    fill = enum.auto()
    hover = enum.auto()
    download = enum.auto()
    userscript = enum.auto()
    spawn = enum.auto()
    delete = enum.auto()
    right_click = enum.auto()


class HintingError(Exception):

    """Exception raised on errors during hinting."""


def on_mode_entered(mode: usertypes.KeyMode, win_id: int) -> None:
    """Stop hinting when insert mode was entered."""
    if mode == usertypes.KeyMode.insert:
        modeman.leave(win_id, usertypes.KeyMode.hint, 'insert mode',
                      maybe=True)


class HintLabel(QLabel):

    """A label for a link.

    Attributes:
        elem: The element this label belongs to.
        _context: The current hinting context.
    """

    def __init__(self, elem: webelem.AbstractWebElement,
                 context: 'HintContext') -> None:
        super().__init__(parent=context.tab)
        self._context = context
        self.elem = elem

        # Make sure we can style the background via a style sheet, and we don't
        # get any extra text indent from Qt.
        # The real stylesheet lives in mainwindow.py for performance reasons..
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setIndent(0)

        self._context.tab.contents_size_changed.connect(self._move_to_elem)
        self._move_to_elem()
        self.show()

    def __repr__(self) -> str:
        try:
            text = self.text()
        except RuntimeError:
            text = '<deleted>'
        return utils.get_repr(self, elem=self.elem, text=text)

    def update_text(self, matched: str, unmatched: str) -> None:
        """Set the text for the hint.

        Args:
            matched: The part of the text which was typed.
            unmatched: The part of the text which was not typed yet.
        """
        if (config.cache['hints.uppercase'] and
                self._context.hint_mode in ['letter', 'word']):
            matched = html.escape(matched.upper())
            unmatched = html.escape(unmatched.upper())
        else:
            matched = html.escape(matched)
            unmatched = html.escape(unmatched)

        if matched:
            match_color = config.cache['colors.hints.match.fg'].name()
            self.setText('<font color="{}">{}</font>{}'.format(
                match_color, matched, unmatched))
        else:
            self.setText(unmatched)
        self.adjustSize()

    @pyqtSlot()
    def _move_to_elem(self) -> None:
        """Reposition the label to its element."""
        if not self.elem.has_frame():
            # This sometimes happens for some reason...
            log.hints.debug("Frame for {!r} vanished!".format(self))
            self.hide()
            return
        no_js = config.cache['hints.find_implementation'] != 'javascript'
        rect = self.elem.rect_on_view(no_js=no_js)
        self.move(rect.x(), rect.y())

    def cleanup(self) -> None:
        """Clean up this element and hide it."""
        self.hide()
        self.deleteLater()


@dataclasses.dataclass
class HintContext:

    """Context namespace used for hinting.

    Attributes:
        all_labels: A list of all HintLabel objects ever created.
        labels: A mapping from key strings to HintLabel objects.
                May contain less elements than `all_labels` due to filtering.
        baseurl: The URL of the current page.
        target: What to do with the opened links.
                normal/current/tab/tab_fg/tab_bg/window: Get passed to
                                                         BrowserTab.
                right_click: Right-click the selected element.
                yank/yank_primary: Yank to clipboard/primary selection.
                run: Run a command.
                fill: Fill commandline with link.
                download: Download the link.
                userscript: Call a custom userscript.
                spawn: Spawn a simple command.
                delete: Delete the selected element.
        to_follow: The link to follow when enter is pressed.
        args: Custom arguments for userscript/spawn
        rapid: Whether to do rapid hinting.
        first_run: Whether the action is run for the 1st time in rapid hinting.
        add_history: Whether to add yanked or spawned link to the history.
        filterstr: Used to save the filter string for restoring in rapid mode.
        tab: The WebTab object we started hinting in.
        group: The group of web elements to hint.
    """

    tab: 'browsertab.AbstractTab'
    target: Target
    rapid: bool
    hint_mode: str
    add_history: bool
    first: bool
    baseurl: QUrl
    args: List[str]
    group: str

    all_labels: List[HintLabel] = dataclasses.field(default_factory=list)
    labels: Dict[str, HintLabel] = dataclasses.field(default_factory=dict)
    to_follow: Optional[str] = None
    first_run: bool = True
    filterstr: Optional[str] = None

    def get_args(self, urlstr: str) -> Sequence[str]:
        """Get the arguments, with {hint-url} replaced by the given URL."""
        args = []
        for arg in self.args:
            arg = arg.replace('{hint-url}', urlstr)
            args.append(arg)
        return args


class HintActions:

    """Actions which can be done after selecting a hint."""

    def __init__(self, win_id: int) -> None:
        self._win_id = win_id

    def click(self, elem: webelem.AbstractWebElement,
              context: HintContext) -> None:
        """Click an element."""
        target_mapping = {
            Target.normal: usertypes.ClickTarget.normal,
            Target.current: usertypes.ClickTarget.normal,
            Target.tab_fg: usertypes.ClickTarget.tab,
            Target.tab_bg: usertypes.ClickTarget.tab_bg,
            Target.window: usertypes.ClickTarget.window,
        }
        if config.val.tabs.background:
            target_mapping[Target.tab] = usertypes.ClickTarget.tab_bg
        else:
            target_mapping[Target.tab] = usertypes.ClickTarget.tab

        if context.target in [Target.normal, Target.current]:
            # Set the pre-jump mark ', so we can jump back here after following
            context.tab.scroller.before_jump_requested.emit()

        try:
            if context.target == Target.hover:
                elem.hover()
            elif context.target == Target.right_click:
                elem.right_click()
            elif context.target == Target.current:
                elem.remove_blank_target()
                elem.click(target_mapping[context.target])
            else:
                elem.click(target_mapping[context.target])
        except webelem.Error as e:
            raise HintingError(str(e))

    def yank(self, url: QUrl, context: HintContext) -> None:
        """Yank an element to the clipboard or primary selection."""
        sel = (context.target == Target.yank_primary and
               utils.supports_selection())

        flags = QUrl.FullyEncoded | QUrl.RemovePassword
        if url.scheme() == 'mailto':
            flags |= QUrl.RemoveScheme
        urlstr = url.toString(flags)  # type: ignore[arg-type]

        new_content = urlstr

        # only second and consecutive yanks are to append to the clipboard
        if context.rapid and not context.first_run:
            try:
                old_content = utils.get_clipboard(selection=sel)
            except utils.ClipboardEmptyError:
                pass
            else:
                new_content = os.linesep.join([old_content, new_content])
        utils.set_clipboard(new_content, selection=sel)

        msg = "Yanked URL to {}: {}".format(
            "primary selection" if sel else "clipboard",
            urlstr)
        message.info(msg)

    def run_cmd(self, url: QUrl, context: HintContext) -> None:
        """Run the command based on a hint URL."""
        urlstr = url.toString(QUrl.FullyEncoded)  # type: ignore[arg-type]
        args = context.get_args(urlstr)
        commandrunner = runners.CommandRunner(self._win_id)
        commandrunner.run_safely(' '.join(args))

    def preset_cmd_text(self, url: QUrl, context: HintContext) -> None:
        """Preset a commandline text based on a hint URL."""
        flags = QUrl.FullyEncoded
        urlstr = url.toDisplayString(flags)  # type: ignore[arg-type]
        args = context.get_args(urlstr)
        text = ' '.join(args)
        if text[0] not in modeparsers.STARTCHARS:
            raise HintingError("Invalid command text '{}'.".format(text))

        cmd = objreg.get('status-command', scope='window', window=self._win_id)
        cmd.set_cmd_text(text)

    def download(self, elem: webelem.AbstractWebElement,
                 context: HintContext) -> None:
        """Download a hint URL.

        Args:
            elem: The QWebElement to download.
            _context: The HintContext to use.
        """
        url = elem.resolve_url(context.baseurl)
        if url is None:
            raise HintingError("No suitable link found for this element.")

        prompt = False if context.rapid else None
        qnam = context.tab.private_api.networkaccessmanager()

        # FIXME:qtwebengine do this with QtWebEngine downloads?
        download_manager = objreg.get('qtnetwork-download-manager')
        download_manager.get(url, qnam=qnam, prompt_download_directory=prompt)

    def call_userscript(self, elem: webelem.AbstractWebElement,
                        context: HintContext) -> None:
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
        url = elem.resolve_url(context.baseurl)
        if url is not None:
            flags = QUrl.FullyEncoded
            env['QUTE_URL'] = url.toString(flags)  # type: ignore[arg-type]

        try:
            userscripts.run_async(context.tab, cmd, *args, win_id=self._win_id,
                                  env=env)
        except userscripts.Error as e:
            raise HintingError(str(e))

    def delete(self, elem: webelem.AbstractWebElement,
               _context: HintContext) -> None:
        elem.delete()

    def spawn(self, url: QUrl, context: HintContext) -> None:
        """Spawn a simple command from a hint.

        Args:
            url: The URL to open as a QUrl.
            context: The HintContext to use.
        """
        urlstr = url.toString(
            QUrl.FullyEncoded | QUrl.RemovePassword)  # type: ignore[arg-type]
        args = context.get_args(urlstr)
        commandrunner = runners.CommandRunner(self._win_id)
        commandrunner.run_safely('spawn ' + ' '.join(args))


_ElemsType = Sequence[webelem.AbstractWebElement]
_HintStringsType = MutableSequence[str]


class HintManager(QObject):

    """Manage drawing hints over links or other elements.

    Class attributes:
        HINT_TEXTS: Text displayed for different hinting modes.

    Attributes:
        _context: The HintContext for the current invocation.
        _win_id: The window ID this HintManager is associated with.
        _tab_id: The tab ID this HintManager is associated with.

    Signals:
        set_text: Request for the statusbar to change its text.
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
        Target.right_click: "Right-click hint",
        Target.download: "Download hint",
        Target.userscript: "Call userscript via hint",
        Target.spawn: "Spawn command via hint",
        Target.delete: "Delete an element",
    }

    set_text = pyqtSignal(str)

    def __init__(self, win_id: int, parent: QObject = None) -> None:
        """Constructor."""
        super().__init__(parent)
        self._win_id = win_id
        self._context: Optional[HintContext] = None
        self._word_hinter = WordHinter()

        self._actions = HintActions(win_id)

        mode_manager = modeman.instance(self._win_id)
        mode_manager.left.connect(self.on_mode_left)

    def _get_text(self) -> str:
        """Get a hint text based on the current context."""
        assert self._context is not None
        text = self.HINT_TEXTS[self._context.target]
        if self._context.rapid:
            text += ' (rapid mode)'
        text += '...'
        return text

    def _cleanup(self) -> None:
        """Clean up after hinting."""
        assert self._context is not None
        for label in self._context.all_labels:
            label.cleanup()

        self.set_text.emit('')

        self._context = None

    def _hint_strings(self, elems: _ElemsType) -> _HintStringsType:
        """Calculate the hint strings for elems.

        Inspired by Vimium.

        Args:
            elems: The elements to get hint strings for.

        Return:
            A list of hint strings, in the same order as the elements.
        """
        if not elems:
            return []

        assert self._context is not None
        hint_mode = self._context.hint_mode
        if hint_mode == 'word':
            try:
                return self._word_hinter.hint(elems)
            except HintingError as e:
                message.error(str(e))
                # falls back on letter hints
        if hint_mode == 'number':
            chars = '0123456789'
        else:
            chars = config.val.hints.chars
        min_chars = config.val.hints.min_chars
        if config.val.hints.scatter and hint_mode != 'number':
            return self._hint_scattered(min_chars, chars, elems)
        else:
            return self._hint_linear(min_chars, chars, elems)

    def _hint_scattered(self, min_chars: int,
                        chars: str,
                        elems: _ElemsType) -> _HintStringsType:
        """Produce scattered hint labels with variable length (like Vimium).

        Args:
            min_chars: The minimum length of labels.
            chars: The alphabet to use for labels.
            elems: The elements to generate labels for.
        """
        # Determine how many digits the link hints will require in the worst
        # case. Usually we do not need all of these digits for every link
        # single hint, so we can show shorter hints for a few of the links.
        needed = max(min_chars, utils.ceil_log(len(elems), len(chars)))

        # Short hints are the number of hints we can possibly show which are
        # (needed - 1) digits in length.
        if needed > min_chars and needed > 1:
            total_space = len(chars) ** needed
            # For each 1 short link being added, len(chars) long links are
            # removed, therefore the space removed is len(chars) - 1.
            short_count = (total_space - len(elems)) // (len(chars) - 1)
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

    def _hint_linear(self, min_chars: int,
                     chars: str,
                     elems: _ElemsType) -> _HintStringsType:
        """Produce linear hint labels with constant length (like dwb).

        Args:
            min_chars: The minimum length of labels.
            chars: The alphabet to use for labels.
            elems: The elements to generate labels for.
        """
        strings = []
        needed = max(min_chars, utils.ceil_log(len(elems), len(chars)))
        for i in range(len(elems)):
            strings.append(self._number_to_hint_str(i, chars, needed))
        return strings

    def _shuffle_hints(self, hints: _HintStringsType,
                       length: int) -> _HintStringsType:
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
        buckets: Sequence[_HintStringsType] = [[] for i in range(length)]
        for i, hint in enumerate(hints):
            buckets[i % len(buckets)].append(hint)
        result: _HintStringsType = []
        for bucket in buckets:
            result += bucket
        return result

    def _number_to_hint_str(self, number: int,
                            chars: str,
                            digits: int = 0) -> str:
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
        hintstr: MutableSequence[str] = []
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

    def _check_args(self, target: Target, *args: str) -> None:
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
                raise cmdutils.CommandError(
                    "'args' is required with target userscript/spawn/run/"
                    "fill.")
        else:
            if args:
                raise cmdutils.CommandError(
                    "'args' is only allowed with target userscript/spawn.")

    def _filter_matches(self, filterstr: Optional[str], elemstr: str) -> bool:
        """Return True if `filterstr` matches `elemstr`."""
        # Empty string and None always match
        if not filterstr:
            return True
        filterstr = filterstr.casefold()
        elemstr = elemstr.casefold()
        # Do multi-word matching
        return all(word in elemstr for word in filterstr.split())

    def _filter_matches_exactly(self, filterstr: str, elemstr: str) -> bool:
        """Return True if `filterstr` exactly matches `elemstr`."""
        # Empty string and None never match
        if not filterstr:
            return False
        filterstr = filterstr.casefold()
        elemstr = elemstr.casefold()
        return filterstr == elemstr

    def _get_keyparser(self,
                       mode: usertypes.KeyMode) -> basekeyparser.BaseKeyParser:
        mode_manager = modeman.instance(self._win_id)
        return mode_manager.parsers[mode]

    def _start_cb(self, elems: _ElemsType) -> None:
        """Initialize the elements and labels based on the context set."""
        if self._context is None:
            log.hints.debug("In _start_cb without context!")
            return

        if not elems:
            message.error("No elements found.")
            return

        # Because _start_cb is called asynchronously, it's possible that the
        # user switched to another tab or closed the tab/window. In that case
        # we should not start hinting.
        tabbed_browser = objreg.get('tabbed-browser', default=None,
                                    scope='window', window=self._win_id)
        tab = tabbed_browser.widget.currentWidget()
        if tab.tab_id != self._context.tab.tab_id:
            log.hints.debug(
                "Current tab changed ({} -> {}) before _start_cb is run."
                .format(self._context.tab.tab_id, tab.tab_id))
            return

        strings = self._hint_strings(elems)
        log.hints.debug("hints: {}".format(', '.join(strings)))

        for elem, string in zip(elems, strings):
            label = HintLabel(elem, self._context)
            label.update_text('', string)
            self._context.all_labels.append(label)
            self._context.labels[string] = label

        keyparser = self._get_keyparser(usertypes.KeyMode.hint)
        keyparser.update_bindings(strings)

        modeman.enter(self._win_id, usertypes.KeyMode.hint,
                      'HintManager.start')

        self.set_text.emit(self._get_text())

        if self._context.first:
            self._fire(strings[0])
            return
        # to make auto_follow == 'always' work
        self._handle_auto_follow()

    @cmdutils.register(instance='hintmanager', scope='window', name='hint',
                       star_args_optional=True, maxsplit=2)
    def start(self,  # pylint: disable=keyword-arg-before-vararg
              group: str = 'all',
              target: Target = Target.normal,
              *args: str,
              mode: str = None,
              add_history: bool = False,
              rapid: bool = False,
              first: bool = False) -> None:
        """Start hinting.

        Args:
            rapid: Whether to do rapid hinting. With rapid hinting, the hint
                   mode isn't left after a hint is followed, so you can easily
                   open multiple links. This is only possible with targets
                   `tab` (with `tabs.background=true`), `tab-bg`,
                   `window`, `run`, `hover`, `userscript` and `spawn`.
            add_history: Whether to add the spawned or yanked link to the
                         browsing history.
            first: Click the first hinted element without prompting.
            group: The element types to hint.

                - `all`: All clickable elements.
                - `links`: Only links.
                - `images`: Only images.
                - `inputs`: Only input fields.

                Custom groups can be added via the `hints.selectors` setting
                and also used here.

            target: What to do with the selected element.

                - `normal`: Open the link.
                - `current`: Open the link in the current tab.
                - `tab`: Open the link in a new tab (honoring the
                         `tabs.background` setting).
                - `tab-fg`: Open the link in a new foreground tab.
                - `tab-bg`: Open the link in a new background tab.
                - `window`: Open the link in a new window.
                - `hover` : Hover over the link.
                - `right-click`: Right-click the element.
                - `yank`: Yank the link to the clipboard.
                - `yank-primary`: Yank the link to the primary selection.
                - `run`: Run the argument as command.
                - `fill`: Fill the commandline with the command given as
                          argument.
                - `download`: Download the link.
                - `userscript`: Call a userscript with `$QUTE_URL` set to the
                                link.
                - `spawn`: Spawn a command.
                - `delete`: Delete the selected element.

            mode: The hinting mode to use.

                - `number`: Use numeric hints.
                - `letter`: Use the chars in the hints.chars setting.
                - `word`: Use hint words based on the html elements and the
                          extra words.

            *args: Arguments for spawn/userscript/run/fill.

                - With `spawn`: The executable and arguments to spawn.
                                `{hint-url}` will get replaced by the selected
                                URL.
                - With `userscript`: The userscript to execute. Either store
                                     the userscript in
                                     `~/.local/share/qutebrowser/userscripts`
                                     (or `$XDG_DATA_HOME`), or use an absolute
                                     path.
                - With `fill`: The command to fill the statusbar with.
                                `{hint-url}` will get replaced by the selected
                                URL.
                - With `run`: Same as `fill`.
        """
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        tab = tabbed_browser.widget.currentWidget()
        if tab is None:
            raise cmdutils.CommandError("No WebView available yet!")

        mode_manager = modeman.instance(self._win_id)
        if mode_manager.mode == usertypes.KeyMode.hint:
            modeman.leave(self._win_id, usertypes.KeyMode.hint, 're-hinting')

        if rapid:
            if target in [Target.tab_bg, Target.window, Target.run,
                          Target.hover, Target.userscript, Target.spawn,
                          Target.download, Target.normal, Target.current,
                          Target.yank, Target.yank_primary]:
                pass
            elif target == Target.tab and config.val.tabs.background:
                pass
            else:
                name = target.name.replace('_', '-')
                raise cmdutils.CommandError("Rapid hinting makes no sense "
                                            "with target {}!".format(name))

        self._check_args(target, *args)

        try:
            baseurl = tabbed_browser.current_url()
        except qtutils.QtValueError:
            raise cmdutils.CommandError("No URL set for this page yet!")

        self._context = HintContext(
            tab=tab,
            target=target,
            rapid=rapid,
            hint_mode=self._get_hint_mode(mode),
            add_history=add_history,
            first=first,
            baseurl=baseurl,
            args=list(args),
            group=group,
        )

        try:
            selector = webelem.css_selector(self._context.group,
                                            self._context.baseurl)
        except webelem.Error as e:
            raise cmdutils.CommandError(str(e))

        self._context.tab.elements.find_css(
            selector,
            callback=self._start_cb,
            error_cb=lambda err: message.error(str(err)),
            only_visible=True)

    def _get_hint_mode(self, mode: Optional[str]) -> str:
        """Get the hinting mode to use based on a mode argument."""
        if mode is None:
            return config.val.hints.mode

        opt = config.instance.get_opt('hints.mode')
        try:
            opt.typ.to_py(mode)
        except configexc.ValidationError as e:
            raise cmdutils.CommandError("Invalid mode: {}".format(e))
        return mode

    def current_mode(self) -> Optional[str]:
        """Return the currently active hinting mode (or None otherwise)."""
        if self._context is None:
            return None

        return self._context.hint_mode

    def _handle_auto_follow(
            self,
            keystr: str = "",
            filterstr: str = "",
            visible: Mapping[str, HintLabel] = None
    ) -> None:
        """Handle the auto_follow option."""
        assert self._context is not None

        if visible is None:
            visible = {string: label
                       for string, label in self._context.labels.items()
                       if label.isVisible()}

        if len(visible) != 1:
            return

        auto_follow = config.val.hints.auto_follow

        if auto_follow == "always":
            follow = True
        elif auto_follow == "unique-match":
            follow = bool(keystr or filterstr)
        elif auto_follow == "full-match":
            elemstr = str(list(visible.values())[0].elem)
            filter_match = self._filter_matches_exactly(filterstr, elemstr)
            follow = (keystr in visible) or filter_match
        else:
            follow = False
            # save the keystr of the only one visible hint to be picked up
            # later by self.hint_follow
            self._context.to_follow = list(visible.keys())[0]

        if follow:
            # apply auto_follow_timeout
            timeout = config.val.hints.auto_follow_timeout
            normal_parser = self._get_keyparser(usertypes.KeyMode.normal)
            normal_parser.set_inhibited_timeout(timeout)
            # unpacking gets us the first (and only) key in the dict.
            self._fire(*visible)

    @pyqtSlot(str)
    def handle_partial_key(self, keystr: str) -> None:
        """Handle a new partial keypress."""
        if self._context is None:
            log.hints.debug("Got key without context!")
            return
        log.hints.debug("Handling new keystring: '{}'".format(keystr))
        for string, label in self._context.labels.items():
            try:
                if string.startswith(keystr):
                    matched = string[:len(keystr)]
                    rest = string[len(keystr):]
                    label.update_text(matched, rest)
                    # Show label again if it was hidden before
                    label.show()
                else:
                    # element doesn't match anymore -> hide it, unless in rapid
                    # mode and hide_unmatched_rapid_hints is false (see #1799)
                    if (not self._context.rapid or
                            config.val.hints.hide_unmatched_rapid_hints):
                        label.hide()
            except webelem.Error:
                pass
        self._handle_auto_follow(keystr=keystr)

    def filter_hints(self, filterstr: Optional[str]) -> None:
        """Filter displayed hints according to a text.

        Args:
            filterstr: The string to filter with, or None to use the filter
                       from previous call (saved in `self._context.filterstr`).
                       If `filterstr` is an empty string or if both `filterstr`
                       and `self._context.filterstr` are None, all hints are
                       shown.
        """
        assert self._context is not None

        if filterstr is None:
            filterstr = self._context.filterstr
        else:
            self._context.filterstr = filterstr

        log.hints.debug("Filtering hints on {!r}".format(filterstr))

        visible = []
        for label in self._context.all_labels:
            try:
                if self._filter_matches(filterstr, str(label.elem)):
                    visible.append(label)
                    # Show label again if it was hidden before
                    label.show()
                else:
                    # element doesn't match anymore -> hide it
                    label.hide()
            except webelem.Error:
                pass

        if not visible:
            # Whoops, filtered all hints
            modeman.leave(self._win_id, usertypes.KeyMode.hint,
                          'all filtered')
            return

        if self._context.hint_mode == 'number':
            # renumber filtered hints
            strings = self._hint_strings([label.elem for label in visible])
            self._context.labels = {}
            for label, string in zip(visible, strings):
                label.update_text('', string)
                self._context.labels[string] = label

            keyparser = self._get_keyparser(usertypes.KeyMode.hint)
            keyparser.update_bindings(strings, preserve_filter=True)

            # Note: filter_hints can be called with non-None filterstr only
            # when number mode is active
            if filterstr is not None:
                # pass self._context.labels as the dict of visible hints
                self._handle_auto_follow(filterstr=filterstr,
                                         visible=self._context.labels)

    def _fire(self, keystr: str) -> None:
        """Fire a completed hint.

        Args:
            keystr: The keychain string to follow.
        """
        assert self._context is not None
        # Handlers which take a QWebElement
        elem_handlers = {
            Target.normal: self._actions.click,
            Target.current: self._actions.click,
            Target.tab: self._actions.click,
            Target.tab_fg: self._actions.click,
            Target.tab_bg: self._actions.click,
            Target.window: self._actions.click,
            Target.hover: self._actions.click,
            Target.right_click: self._actions.click,
            # _download needs a QWebElement to get the frame.
            Target.download: self._actions.download,
            Target.userscript: self._actions.call_userscript,
            Target.delete: self._actions.delete,
        }
        # Handlers which take a QUrl
        url_handlers = {
            Target.yank: self._actions.yank,
            Target.yank_primary: self._actions.yank,
            Target.run: self._actions.run_cmd,
            Target.fill: self._actions.preset_cmd_text,
            Target.spawn: self._actions.spawn,
        }
        elem = self._context.labels[keystr].elem

        if not elem.has_frame():
            message.error("This element has no webframe.")
            return

        if self._context.target in elem_handlers:
            handler = functools.partial(elem_handlers[self._context.target],
                                        elem, self._context)
        elif self._context.target in url_handlers:
            url = elem.resolve_url(self._context.baseurl)
            if url is None:
                message.error("No suitable link found for this element.")
                return
            handler = functools.partial(url_handlers[self._context.target],
                                        url, self._context)
            if self._context.add_history:
                history.web_history.add_url(url, "")
        else:
            raise ValueError("No suitable handler found!")

        if not self._context.rapid:
            modeman.leave(self._win_id, usertypes.KeyMode.hint, 'followed',
                          maybe=True)
        else:
            # Reset filtering
            self.filter_hints(None)
            # Undo keystring highlighting
            for string, label in self._context.labels.items():
                label.update_text('', string)

        try:
            handler()
        except HintingError as e:
            message.error(str(e))

        if self._context is not None:
            self._context.first_run = False

    @cmdutils.register(instance='hintmanager', scope='window',
                       modes=[usertypes.KeyMode.hint], deprecated_name='follow-hint')
    def hint_follow(self, select: bool = False, keystring: str = None) -> None:
        """Follow a hint.

        Args:
            select: Only select the given hint, don't necessarily follow it.
            keystring: The hint to follow, or None.
        """
        assert self._context is not None
        if keystring is None:
            if self._context.to_follow is None:
                raise cmdutils.CommandError("No hint to follow")
            if select:
                raise cmdutils.CommandError("Can't use --select without hint.")
            keystring = self._context.to_follow
        elif keystring not in self._context.labels:
            raise cmdutils.CommandError("No hint {}!".format(keystring))

        if select:
            self.handle_partial_key(keystring)
        else:
            self._fire(keystring)

    @cmdutils.register(instance='hintmanager', scope='window',
                       modes=[usertypes.KeyMode.hint])
    def hints_cycle(self, reverse: bool = False) -> None:
        """Bring hints covered by other hints to the foreground.

        Args:
            reverse: Cycle in reverse direction.
        """
        hintcontext = self._context
        if hintcontext is None:
            raise cmdutils.CommandError("Hints not available.")
        labels = hintcontext.all_labels
        overlap.cycle(labels, reverse)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode: usertypes.KeyMode) -> None:
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

    def __init__(self) -> None:
        # will be initialized on first use.
        self.words: Set[str] = set()
        self.dictionary = None

    def ensure_initialized(self) -> None:
        """Generate the used words if yet uninitialized."""
        dictionary = config.val.hints.dictionary
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
            except OSError as e:
                error = "Word hints requires reading the file at {}: {}"
                raise HintingError(error.format(dictionary, str(e)))

    def extract_tag_words(
            self, elem: webelem.AbstractWebElement
    ) -> Iterator[str]:
        """Extract tag words form the given element."""
        _extractor_type = Callable[[webelem.AbstractWebElement], str]
        attr_extractors: Mapping[str, _extractor_type] = {
            "alt": lambda elem: elem["alt"],
            "name": lambda elem: elem["name"],
            "title": lambda elem: elem["title"],
            "placeholder": lambda elem: elem["placeholder"],
            "src": lambda elem: elem["src"].split('/')[-1],
            "href": lambda elem: elem["href"].split('/')[-1],
            "text": str,
        }

        extractable_attrs = collections.defaultdict(list, {
            "img": ["alt", "title", "src"],
            "a": ["title", "href", "text"],
            "input": ["name", "placeholder"],
            "textarea": ["name", "placeholder"],
            "button": ["text"]
        })

        return (attr_extractors[attr](elem)
                for attr in extractable_attrs[elem.tag_name()]
                if attr in elem or attr == "text")

    def tag_words_to_hints(
            self,
            words: Iterable[str]
    ) -> Iterator[str]:
        """Take words and transform them to proper hints if possible."""
        for candidate in words:
            if not candidate:
                continue
            match = re.search('[A-Za-z]{3,}', candidate)
            if not match:
                continue
            if 4 < match.end() - match.start() < 8:
                yield candidate[match.start():match.end()].lower()

    def any_prefix(self, hint: str, existing: Iterable[str]) -> bool:
        return any(hint.startswith(e) or e.startswith(hint) for e in existing)

    def filter_prefixes(
            self,
            hints: Iterable[str],
            existing: Iterable[str]
    ) -> Iterator[str]:
        """Filter hints which don't start with the given prefix."""
        return (h for h in hints if not self.any_prefix(h, existing))

    def new_hint_for(self, elem: webelem.AbstractWebElement,
                     existing: Iterable[str],
                     fallback: Iterable[str]) -> Optional[str]:
        """Return a hint for elem, not conflicting with the existing."""
        new = self.tag_words_to_hints(self.extract_tag_words(elem))
        new_no_prefixes = self.filter_prefixes(new, existing)
        fallback_no_prefixes = self.filter_prefixes(fallback, existing)
        # either the first good, or None
        return (next(new_no_prefixes, None) or
                next(fallback_no_prefixes, None))

    def hint(self, elems: _ElemsType) -> _HintStringsType:
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
        used_hints: Set[str] = set()
        words = iter(self.words)
        for elem in elems:
            hint = self.new_hint_for(elem, used_hints, words)
            if not hint:
                raise HintingError("Not enough words in the dictionary.")
            used_hints.add(hint)
            hints.append(hint)
        return hints
