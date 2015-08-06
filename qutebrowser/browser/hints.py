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

"""A HintManager to draw hints over links."""

import math
import functools
import collections

from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QObject, QEvent, Qt, QUrl,
                          QTimer)
from PyQt5.QtGui import QMouseEvent, QClipboard
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebKit import QWebElement
from PyQt5.QtWebKitWidgets import QWebPage

from qutebrowser.config import config
from qutebrowser.keyinput import modeman, modeparsers
from qutebrowser.browser import webelem
from qutebrowser.commands import userscripts, cmdexc, cmdutils, runners
from qutebrowser.utils import usertypes, log, qtutils, message, objreg
from qutebrowser.misc import guiprocess


ElemTuple = collections.namedtuple('ElemTuple', ['elem', 'label'])


Target = usertypes.enum('Target', ['normal', 'tab', 'tab_fg', 'tab_bg',
                                   'window', 'yank', 'yank_primary', 'run',
                                   'fill', 'hover', 'rapid', 'rapid_win',
                                   'download', 'userscript', 'spawn'])


@pyqtSlot(usertypes.KeyMode)
def on_mode_entered(mode, win_id):
    """Stop hinting when insert mode was entered."""
    if mode == usertypes.KeyMode.insert:
        modeman.maybe_leave(win_id, usertypes.KeyMode.hint, 'insert mode')


class HintContext:

    """Context namespace used for hinting.

    Attributes:
        frames: The QWebFrames to use.
        destroyed_frames: id()'s of QWebFrames which have been destroyed.
                          (Workaround for https://github.com/The-Compiler/qutebrowser/issues/152)
        elems: A mapping from key strings to (elem, label) namedtuples.
        baseurl: The URL of the current page.
        target: What to do with the opened links.
                normal/tab/tab_fg/tab_bg/window: Get passed to BrowserTab.
                yank/yank_primary: Yank to clipboard/primary selection.
                run: Run a command.
                fill: Fill commandline with link.
                rapid: Rapid mode with background tabs
                download: Download the link.
                userscript: Call a custom userscript.
                spawn: Spawn a simple command.
        to_follow: The link to follow when enter is pressed.
        args: Custom arguments for userscript/spawn
        rapid: Whether to do rapid hinting.
        mainframe: The main QWebFrame where we started hinting in.
        group: The group of web elements to hint.
    """

    def __init__(self):
        self.elems = {}
        self.target = None
        self.baseurl = None
        self.to_follow = None
        self.rapid = False
        self.frames = []
        self.destroyed_frames = []
        self.args = []
        self.mainframe = None
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

    Signals:
        mouse_event: Mouse event to be posted in the web view.
                     arg: A QMouseEvent
        start_hinting: Emitted when hinting starts, before a link is clicked.
                       arg: The ClickTarget to use.
        stop_hinting: Emitted after a link was clicked.
    """

    HINT_TEXTS = {
        Target.normal: "Follow hint",
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
        for elem in self._context.elems.values():
            try:
                elem.label.removeFromDocument()
            except webelem.IsNullError:
                pass
        for f in self._context.frames:
            log.hints.debug("Disconnecting frame {}".format(f))
            if id(f) in self._context.destroyed_frames:
                # WORKAROUND for
                # https://github.com/The-Compiler/qutebrowser/issues/152
                log.hints.debug("Frame has been destroyed, ignoring.")
                continue
            try:
                f.contentsSizeChanged.disconnect(self.on_contents_size_changed)
            except TypeError:
                # It seems we can get this here:
                #   TypeError: disconnect() failed between
                #   'contentsSizeChanged' and 'on_contents_size_changed'
                # See # https://github.com/The-Compiler/qutebrowser/issues/263
                pass
            log.hints.debug("Disconnected.")
        text = self._get_text()
        message_bridge = objreg.get('message-bridge', scope='window',
                                    window=self._win_id)
        message_bridge.maybe_reset_text(text)
        self._context = None

    def _hint_strings(self, elems):
        """Calculate the hint strings for elems.

        Inspired by Vimium.

        Args:
            elems: The elements to get hint strings for.

        Return:
            A list of hint strings, in the same order as the elements.
        """
        if config.get('hints', 'mode') == 'number':
            chars = '0123456789'
        else:
            chars = config.get('hints', 'chars')
        min_chars = config.get('hints', 'min-chars')
        if config.get('hints', 'scatter'):
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
        display = elem.styleProperty('display', QWebElement.InlineStyle)
        return display == 'none'

    def _show_elem(self, elem):
        """Show a given element."""
        elem.setStyleProperty('display', 'inline !important')

    def _hide_elem(self, elem):
        """Hide a given element."""
        elem.setStyleProperty('display', 'none !important')

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
            ('position', 'absolute !important'),
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
            label.setStyleProperty(k, v)
        self._set_style_position(elem, label)

    def _set_style_position(self, elem, label):
        """Set the CSS position of the label element.

        Args:
            elem: The QWebElement to set the style attributes for.
            label: The label QWebElement.
        """
        rect = elem.geometry()
        left = rect.x()
        top = rect.y()
        zoom = elem.webFrame().zoomFactor()
        if not config.get('ui', 'zoom-text-only'):
            left /= zoom
            top /= zoom
        log.hints.vdebug("Drawing label '{!r}' at {}/{} for element '{!r}', "
                         "zoom level {}".format(label, left, top, elem, zoom))
        label.setStyleProperty('left', '{}px !important'.format(left))
        label.setStyleProperty('top', '{}px !important'.format(top))

    def _draw_label(self, elem, string):
        """Draw a hint label over an element.

        Args:
            elem: The QWebElement to use.
            string: The hint string to print.

        Return:
            The newly created label element
        """
        doc = elem.webFrame().documentElement()
        # It seems impossible to create an empty QWebElement for which isNull()
        # is false so we can work with it.
        # As a workaround, we use appendInside() with markup as argument, and
        # then use lastChild() to get a reference to it.
        # See: http://stackoverflow.com/q/7364852/2085149
        body = doc.findFirst('body')
        if not body.isNull():
            parent = body
        else:
            parent = doc
        parent.appendInside('<span></span>')
        label = webelem.WebElementWrapper(parent.lastChild())
        label['class'] = 'qutehint'
        self._set_style_properties(elem, label)
        label.setPlainText(string)
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
            Target.rapid: usertypes.ClickTarget.tab_bg,
            Target.rapid_win: usertypes.ClickTarget.window,
            Target.normal: usertypes.ClickTarget.normal,
            Target.tab_fg: usertypes.ClickTarget.tab,
            Target.tab_bg: usertypes.ClickTarget.tab_bg,
            Target.window: usertypes.ClickTarget.window,
            Target.hover: usertypes.ClickTarget.normal,
        }
        if config.get('tabs', 'background-tabs'):
            target_mapping[Target.tab] = usertypes.ClickTarget.tab_bg
        else:
            target_mapping[Target.tab] = usertypes.ClickTarget.tab
        # FIXME Instead of clicking the center, we could have nicer heuristics.
        # e.g. parse (-webkit-)border-radius correctly and click text fields at
        # the bottom right, and everything else on the top left or so.
        # https://github.com/The-Compiler/qutebrowser/issues/70
        pos = elem.rect_on_view().center()
        action = "Hovering" if context.target == Target.hover else "Clicking"
        log.hints.debug("{} on '{}' at {}/{}".format(
            action, elem, pos.x(), pos.y()))
        self.start_hinting.emit(target_mapping[context.target])
        if context.target in [Target.tab, Target.tab_fg, Target.tab_bg,
                              Target.window, Target.rapid, Target.rapid_win]:
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
        for evt in events:
            self.mouse_event.emit(evt)
        if elem.is_text_input() and elem.is_editable():
            QTimer.singleShot(0, functools.partial(
                elem.webFrame().page().triggerAction,
                QWebPage.MoveToEndOfDocument))
        QTimer.singleShot(0, self.stop_hinting.emit)

    def _yank(self, url, context):
        """Yank an element to the clipboard or primary selection.

        Args:
            url: The URL to open as a QUrl.
            context: The HintContext to use.
        """
        sel = context.target == Target.yank_primary
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        urlstr = url.toString(QUrl.FullyEncoded | QUrl.RemovePassword)
        QApplication.clipboard().setText(urlstr, mode)
        message.info(self._win_id, "URL yanked to {}".format(
            "primary selection" if sel else "clipboard"))

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
        download_manager.get(url, page=elem.webFrame().page(),
                             prompt_download_directory=prompt)

    def _call_userscript(self, elem, context):
        """Call a userscript from a hint.

        Args:
            elem: The QWebElement to use in the userscript.
            context: The HintContext to use.
        """
        cmd = context.args[0]
        args = context.args[1:]
        frame = context.mainframe
        env = {
            'QUTE_MODE': 'hints',
            'QUTE_SELECTED_TEXT': str(elem),
            'QUTE_SELECTED_HTML': elem.toOuterXml(),
        }
        url = self._resolve_url(elem, context.baseurl)
        if url is not None:
            env['QUTE_URL'] = url.toString(QUrl.FullyEncoded)
        env.update(userscripts.store_source(frame))
        userscripts.run(cmd, *args, win_id=self._win_id, env=env)

    def _spawn(self, url, context):
        """Spawn a simple command from a hint.

        Args:
            url: The URL to open as a QUrl.
            context: The HintContext to use.
        """
        urlstr = url.toString(QUrl.FullyEncoded | QUrl.RemovePassword)
        args = context.get_args(urlstr)
        cmd, *args = args
        proc = guiprocess.GUIProcess(self._win_id, what='command', parent=self)
        proc.start(cmd, args)

    def _resolve_url(self, elem, baseurl):
        """Resolve a URL and check if we want to keep it.

        Args:
            elem: The QWebElement to get the URL of.
            baseurl: The baseurl of the current tab.

        Return:
            A QUrl with the absolute URL, or None.
        """
        for attr in ('href', 'src'):
            if attr in elem:
                text = elem[attr]
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

    def _find_prevnext(self, frame, prev=False):
        """Find a prev/next element in frame."""
        # First check for <link rel="prev(ious)|next">
        elems = frame.findAllElements(
            webelem.SELECTORS[webelem.Group.links])
        rel_values = ('prev', 'previous') if prev else ('next')
        for e in elems:
            e = webelem.WebElementWrapper(e)
            try:
                rel_attr = e['rel']
            except KeyError:
                continue
            if rel_attr in rel_values:
                log.hints.debug("Found '{}' with rel={}".format(
                    e.debug_text(), rel_attr))
                return e
        # Then check for regular links/buttons.
        elems = frame.findAllElements(
            webelem.SELECTORS[webelem.Group.prevnext])
        elems = [webelem.WebElementWrapper(e) for e in elems]
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

    def _connect_frame_signals(self):
        """Connect the contentsSizeChanged signals to all frames."""
        for f in self._context.frames:
            log.hints.debug("Connecting frame {}".format(f))
            f.contentsSizeChanged.connect(self.on_contents_size_changed)

    def _check_args(self, target, *args):
        """Check the arguments passed to start() and raise if they're wrong.

        Args:
            target: A Target enum member.
            args: Arguments for userscript/download
        """
        if not isinstance(target, Target):
            raise TypeError("Target {} is no Target member!".format(target))
        if target in (Target.userscript, Target.spawn, Target.run,
                      Target.fill):
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
        elems = []
        for f in self._context.frames:
            elems += f.findAllElements(webelem.SELECTORS[self._context.group])
        elems = [e for e in elems
                 if webelem.is_visible(e, self._context.mainframe)]
        # We wrap the elements late for performance reasons, as wrapping 1000s
        # of elements (with ~50 methods each) just takes too much time...
        elems = [webelem.WebElementWrapper(e) for e in elems]
        filterfunc = webelem.FILTERS.get(self._context.group, lambda e: True)
        elems = [e for e in elems if filterfunc(e)]
        if not elems:
            raise cmdexc.CommandError("No elements found.")
        strings = self._hint_strings(elems)
        for e, string in zip(elems, strings):
            label = self._draw_label(e, string)
            self._context.elems[string] = ElemTuple(e, label)
        keyparsers = objreg.get('keyparsers', scope='window',
                                window=self._win_id)
        keyparser = keyparsers[usertypes.KeyMode.hint]
        keyparser.update_bindings(strings)

    def follow_prevnext(self, frame, baseurl, prev=False, tab=False,
                        background=False, window=False):
        """Click a "previous"/"next" element on the page.

        Args:
            frame: The frame where the element is in.
            baseurl: The base URL of the current tab.
            prev: True to open a "previous" link, False to open a "next" link.
            tab: True to open in a new tab, False for the current tab.
            background: True to open in a background tab.
            window: True to open in a new window, False for the current one.
        """
        from qutebrowser.mainwindow import mainwindow
        elem = self._find_prevnext(frame, prev)
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
            webview = objreg.get('webview', scope='tab', window=self._win_id,
                                 tab=self._tab_id)
            webview.openurl(url)

    @cmdutils.register(instance='hintmanager', scope='tab', name='hint',
                       win_id='win_id')
    def start(self, rapid=False, group=webelem.Group.all, target=Target.normal,
              *args: {'nargs': '*'}, win_id):
        """Start hinting.

        Args:
            rapid: Whether to do rapid hinting. This is only possible with
                   targets `tab` (with background-tabs=true), `tab-bg`,
                   `window`, `run`, `hover`, `userscript` and `spawn`.
            group: The hinting mode to use.

                - `all`: All clickable elements.
                - `links`: Only links.
                - `images`: Only images.

            target: What to do with the selected element.

                - `normal`: Open the link in the current tab.
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
                - With `userscript`: The userscript to execute.
                - With `fill`: The command to fill the statusbar with.
                                `{hint-url}` will get replaced by the selected
                                URL.
                - With `run`: Same as `fill`.
        """
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        widget = tabbed_browser.currentWidget()
        if widget is None:
            raise cmdexc.CommandError("No WebView available yet!")
        mainframe = widget.page().mainFrame()
        if mainframe is None:
            raise cmdexc.CommandError("No frame focused!")
        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=self._win_id)
        if mode_manager.mode == usertypes.KeyMode.hint:
            modeman.leave(win_id, usertypes.KeyMode.hint, 're-hinting')

        if rapid:
            if target in [Target.tab_bg, Target.window, Target.run,
                          Target.hover, Target.userscript, Target.spawn,
                          Target.download]:
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
        self._context.target = target
        self._context.rapid = rapid
        try:
            self._context.baseurl = tabbed_browser.current_url()
        except qtutils.QtValueError:
            raise cmdexc.CommandError("No URL set for this page yet!")
        self._context.frames = webelem.get_child_frames(mainframe)
        for frame in self._context.frames:
            # WORKAROUND for
            # https://github.com/The-Compiler/qutebrowser/issues/152
            frame.destroyed.connect(functools.partial(
                self._context.destroyed_frames.append, id(frame)))
        self._context.args = args
        self._context.mainframe = mainframe
        self._context.group = group
        self._handle_old_rapid_targets(win_id)
        self._init_elements()
        message_bridge = objreg.get('message-bridge', scope='window',
                                    window=self._win_id)
        message_bridge.set_text(self._get_text())
        self._connect_frame_signals()
        modeman.enter(self._win_id, usertypes.KeyMode.hint,
                      'HintManager.start')

    def _handle_old_rapid_targets(self, win_id):
        """Switch to the new way for rapid hinting with a rapid target.

        Args:
            win_id: The window ID to display the warning in.

        DEPRECATED.
        """
        old_rapid_targets = {
            Target.rapid: Target.tab_bg,
            Target.rapid_win: Target.window,
        }
        target = self._context.target
        if target in old_rapid_targets:
            self._context.target = old_rapid_targets[target]
            self._context.rapid = True
            name = target.name.replace('_', '-')
            group_name = self._context.group.name.replace('_', '-')
            new_name = self._context.target.name.replace('_', '-')
            message.warning(
                win_id, ':hint with target {} is deprecated, use :hint '
                '--rapid {} {} instead!'.format(name, group_name, new_name))

    def handle_partial_key(self, keystr):
        """Handle a new partial keypress."""
        log.hints.debug("Handling new keystring: '{}'".format(keystr))
        for (string, elems) in self._context.elems.items():
            try:
                if string.startswith(keystr):
                    matched = string[:len(keystr)]
                    rest = string[len(keystr):]
                    match_color = config.get('colors', 'hints.fg.match')
                    elems.label.setInnerXml(
                        '<font color="{}">{}</font>{}'.format(
                            match_color, matched, rest))
                    if self._is_hidden(elems.label):
                        # hidden element which matches again -> show it
                        self._show_elem(elems.label)
                else:
                    # element doesn't match anymore -> hide it
                    self._hide_elem(elems.label)
            except webelem.IsNullError:
                pass

    def filter_hints(self, filterstr):
        """Filter displayed hints according to a text.

        Args:
            filterstr: The string to filer with, or None to show all.
        """
        for elems in self._context.elems.values():
            try:
                if (filterstr is None or
                        str(elems.elem).lower().startswith(filterstr)):
                    if self._is_hidden(elems.label):
                        # hidden element which matches again -> show it
                        self._show_elem(elems.label)
                else:
                    # element doesn't match anymore -> hide it
                    self._hide_elem(elems.label)
            except webelem.IsNullError:
                pass
        visible = {}
        for k, e in self._context.elems.items():
            try:
                if not self._is_hidden(e.label):
                    visible[k] = e
            except webelem.IsNullError:
                pass
        if not visible:
            # Whoops, filtered all hints
            modeman.leave(self._win_id, usertypes.KeyMode.hint, 'all filtered')
        elif len(visible) == 1 and config.get('hints', 'auto-follow'):
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
        if elem.webFrame() is None:
            message.error(self._win_id, "This element has no webframe.",
                          immediately=True)
            return
        if self._context.target in elem_handlers:
            handler = functools.partial(
                elem_handlers[self._context.target], elem, self._context)
        elif self._context.target in url_handlers:
            url = self._resolve_url(elem, self._context.baseurl)
            if url is None:
                self._show_url_error()
                return
            handler = functools.partial(
                url_handlers[self._context.target], url, self._context)
        else:
            raise ValueError("No suitable handler found!")
        if not self._context.rapid:
            modeman.maybe_leave(self._win_id, usertypes.KeyMode.hint,
                                'followed')
        else:
            # Show all hints again
            self.filter_hints(None)
            # Undo keystring highlighting
            for (string, elems) in self._context.elems.items():
                elems.label.setInnerXml(string)
        handler()

    @cmdutils.register(instance='hintmanager', scope='tab', hide=True)
    def follow_hint(self):
        """Follow the currently selected hint."""
        if not self._context.to_follow:
            raise cmdexc.CommandError("No hint to follow")
        self.fire(self._context.to_follow, force=True)

    @pyqtSlot('QSize')
    def on_contents_size_changed(self, _size):
        """Reposition hints if contents size changed."""
        log.hints.debug("Contents size changed...!")
        for elems in self._context.elems.values():
            try:
                if elems.elem.webFrame() is None:
                    # This sometimes happens for some reason...
                    elems.label.removeFromDocument()
                    continue
                self._set_style_position(elems.elem, elems.label)
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
