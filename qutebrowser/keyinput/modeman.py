# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Mode manager (per window) which handles the current keyboard mode."""

from qutebrowser.qt.widgets import QApplication

import functools
from typing import Mapping, Callable, MutableMapping, Union, Set, cast, List

from qutebrowser.qt import machinery
from qutebrowser.qt.core import pyqtSlot, pyqtSignal, Qt, QObject, QEvent
from qutebrowser.qt.gui import QKeyEvent, QKeySequence

from qutebrowser.commands import runners
from qutebrowser.keyinput import modeparsers, basekeyparser, keyutils
from qutebrowser.config import config
from qutebrowser.api import cmdutils
from qutebrowser.utils import usertypes, log, objreg, utils, qtutils
from qutebrowser.browser import hints
from qutebrowser.misc import objects

INPUT_MODES = [usertypes.KeyMode.insert, usertypes.KeyMode.passthrough]
PROMPT_MODES = [usertypes.KeyMode.prompt, usertypes.KeyMode.yesno]

# FIXME:mypy TypedDict?
ParserDictType = MutableMapping[usertypes.KeyMode, basekeyparser.BaseKeyParser]


class NotInModeError(Exception):

    """Exception raised when we want to leave a mode we're not in."""


class UnavailableError(Exception):

    """Exception raised when trying to access modeman before initialization.

    Thrown by instance() if modeman has not been initialized yet.
    """


def init(win_id: int, parent: QObject) -> 'ModeManager':
    """Initialize the mode manager and the keyparsers for the given win_id."""
    commandrunner = runners.CommandRunner(win_id)

    modeman = ModeManager(win_id, parent)
    objreg.register('mode-manager', modeman, scope='window', window=win_id)

    hintmanager = hints.HintManager(win_id, parent=parent)
    objreg.register('hintmanager', hintmanager, scope='window',
                    window=win_id, command_only=True)
    modeman.hintmanager = hintmanager

    log_sensitive_keys = 'log-sensitive-keys' in objects.debug_flags

    keyparsers: ParserDictType = {
        usertypes.KeyMode.normal:
            modeparsers.NormalKeyParser(
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman),

        usertypes.KeyMode.hint:
            modeparsers.HintKeyParser(
                win_id=win_id,
                commandrunner=commandrunner,
                hintmanager=hintmanager,
                parent=modeman),

        usertypes.KeyMode.insert:
            modeparsers.CommandKeyParser(
                mode=usertypes.KeyMode.insert,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman,
                passthrough=True,
                do_log=log_sensitive_keys,
                supports_count=False,
                allow_partial_timeout=True),

        usertypes.KeyMode.passthrough:
            modeparsers.CommandKeyParser(
                mode=usertypes.KeyMode.passthrough,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman,
                passthrough=True,
                do_log=log_sensitive_keys,
                supports_count=False,
                allow_partial_timeout=True),

        usertypes.KeyMode.command:
            modeparsers.CommandKeyParser(
                mode=usertypes.KeyMode.command,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman,
                passthrough=True,
                do_log=log_sensitive_keys,
                supports_count=False,
                allow_partial_timeout=True,
                allow_forward=True)
            .set_forward_widget_name('status-command'),

        usertypes.KeyMode.prompt:
            modeparsers.CommandKeyParser(
                mode=usertypes.KeyMode.prompt,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman,
                passthrough=True,
                do_log=log_sensitive_keys,
                supports_count=False,
                # Maybe in the future implement this, but for the time being its
                # infeasible as 'prompt-container' is registered as command-only.
                # Plus, I imagine the use case for such a thing is quite rare.
                # (The forward_widget_name would be 'prompt-container')
                allow_forward=False,
                allow_partial_timeout=False),

        usertypes.KeyMode.yesno:
            modeparsers.CommandKeyParser(
                mode=usertypes.KeyMode.yesno,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman,
                supports_count=False,
                # Similar story to prompt mode
                allow_forward=False,
                allow_partial_timeout=False),

        usertypes.KeyMode.caret:
            modeparsers.CommandKeyParser(
                mode=usertypes.KeyMode.caret,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman,
                passthrough=True,
                allow_partial_timeout=True),

        usertypes.KeyMode.set_mark:
            modeparsers.RegisterKeyParser(
                mode=usertypes.KeyMode.set_mark,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman),

        usertypes.KeyMode.jump_mark:
            modeparsers.RegisterKeyParser(
                mode=usertypes.KeyMode.jump_mark,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman),

        usertypes.KeyMode.record_macro:
            modeparsers.RegisterKeyParser(
                mode=usertypes.KeyMode.record_macro,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman),

        usertypes.KeyMode.run_macro:
            modeparsers.RegisterKeyParser(
                mode=usertypes.KeyMode.run_macro,
                win_id=win_id,
                commandrunner=commandrunner,
                parent=modeman),
    }

    for mode, parser in keyparsers.items():
        modeman.register(mode, parser)

    return modeman


def instance(win_id: Union[int, str]) -> 'ModeManager':
    """Get a modemanager object.

    Raises UnavailableError if there is no instance available yet.
    """
    mode_manager = objreg.get('mode-manager', scope='window', window=win_id,
                              default=None)
    if mode_manager is not None:
        return mode_manager
    else:
        raise UnavailableError("ModeManager is not initialized yet.")


def enter(win_id: int,
          mode: usertypes.KeyMode,
          reason: str = None,
          only_if_normal: bool = False) -> None:
    """Enter the mode 'mode'."""
    instance(win_id).enter(mode, reason, only_if_normal)


def leave(win_id: int,
          mode: usertypes.KeyMode,
          reason: str = None, *,
          maybe: bool = False) -> None:
    """Leave the mode 'mode'."""
    instance(win_id).leave(mode, reason, maybe=maybe)


class ModeManager(QObject):

    """Manager for keyboard modes.

    Attributes:
        mode: The mode we're currently in.
        hintmanager: The HintManager associated with this window.
        _win_id: The window ID of this ModeManager
        _prev_mode: Mode before a prompt popped up
        parsers: A dictionary of modes and their keyparsers.
        _forward_unbound_keys: If we should forward unbound keys.
        _releaseevents_to_pass: A set of KeyEvents where the keyPressEvent was
                                passed through, so the release event should as
                                well.
        _partial_timer: The timer which forwards partial keys after no key has
                        been pressed for a timeout period.

    Signals:
        entered: Emitted when a mode is entered.
                 arg1: The mode which has been entered.
                 arg2: The window ID of this mode manager.
        left:  Emitted when a mode is left.
                 arg1: The mode which has been left.
                 arg2: The new current mode.
                 arg3: The window ID of this mode manager.
        keystring_updated: Emitted when the keystring was updated in any mode.
                           arg1: The mode in which the keystring has been
                                 updated.
                           arg2: The new key string.
        forward_partial_key: Emitted when a partial key should be forwarded.
                             arg1: The mode in which the partial key was
                                   pressed.
                             arg2: Text expected to be forwarded (used solely
                                   for debug info, default is None).
    """

    entered = pyqtSignal(usertypes.KeyMode, int)
    left = pyqtSignal(usertypes.KeyMode, usertypes.KeyMode, int)
    keystring_updated = pyqtSignal(usertypes.KeyMode, str)
    forward_partial_key = pyqtSignal(usertypes.KeyMode, str)

    def __init__(self, win_id: int, parent: QObject = None) -> None:
        super().__init__(parent)
        self._win_id = win_id
        self.parsers: ParserDictType = {}
        self._prev_mode = usertypes.KeyMode.normal
        self.mode = usertypes.KeyMode.normal
        self._releaseevents_to_pass: Set[keyutils.KeyEvent] = set()
        # Set after __init__
        self.hintmanager = cast(hints.HintManager, None)
        self._partial_match_events: List[keyutils.QueuedKeyEventPair] = []
        self.forward_partial_key.connect(self.forward_partial_match_event)
        self._partial_timer = usertypes.Timer(self, 'partial-match')
        self._partial_timer.setSingleShot(True)

    def __repr__(self) -> str:
        return utils.get_repr(self, mode=self.mode)

    def _handle_keypress(self, event: QKeyEvent, *,  # noqa: C901
                         dry_run: bool = False) -> bool:
        """Handle filtering of KeyPress events.

        Args:
            event: The KeyPress to examine.
            dry_run: Don't actually handle the key, only filter it.

        Return:
            True if event should be filtered, False otherwise.
        """
        curmode = self.mode
        parser = self.parsers[curmode]
        do_log = parser.get_do_log()
        if do_log:
            log.modes.debug("got keypress in mode {} - delegating to "
                            "{}".format(curmode, utils.qualname(parser)))

        had_empty_queue = not self._partial_match_events
        if parser.allow_forward and (not dry_run) and (not had_empty_queue):
            # Immediately record the event so that parser.handle may forward if
            # appropriate from its logic.
            if do_log:
                log.modes.debug("Enqueuing key event due to non-empty queue: "
                                "{}".format(event))
            self._partial_match_events.append(
                keyutils.QueuedKeyEventPair.from_event_press(event))

        if keyutils.KeyInfo.from_event(event).is_modifier_key():
            if do_log:
                log.modes.debug("Ignoring, only modifier")
            if not dry_run:
                # Since this is a NoMatch without a call to parser.handle, we
                # must manually forward the events
                self.forward_all_partial_match_events(self.mode,
                    stop_timer=True)
            match = QKeySequence.SequenceMatch.NoMatch
        else:
            match = parser.handle(event, dry_run=dry_run)

        if match == QKeySequence.SequenceMatch.ExactMatch:
            filter_this = True
            if not dry_run:
                if do_log:
                    log.modes.debug("Stopping partial timer.")
                self._stop_partial_timer()
                if do_log:
                    log.modes.debug("Clearing partial match events.")
                self.clear_partial_match_events()
        elif match == QKeySequence.SequenceMatch.PartialMatch:
            filter_this = True
            if parser.allow_forward and (not dry_run):
                if had_empty_queue:
                    # Begin recording partial match events
                    if do_log:
                        log.modes.debug("Enqueuing key event as first entry "
                                        "in an empty queue: {}".format(event))
                    self._partial_match_events.append(
                        keyutils.QueuedKeyEventPair.from_event_press(event))
                if do_log:
                    log.modes.debug("Starting partial timer.")
                self._start_partial_timer()
        elif not had_empty_queue:
            # Since partial events were recorded, this event must be filtered.
            # Since a NoMatch was found, this event has already been forwarded
            filter_this = True
            if not dry_run:
                if do_log:
                    log.modes.debug("Stopping partial timer.")
                self._stop_partial_timer()
        else:
            key_info = keyutils.KeyInfo.from_event(event)
            filter_this = self._should_filter_event(key_info, parser)

        if not filter_this and not dry_run:
            if do_log:
                log.modes.debug("Adding release event for pass: "
                                "{}".format(event))
            self._releaseevents_to_pass.add(keyutils.KeyEvent.from_event(event))

        if do_log:
            if machinery.IS_QT5:  # FIXME:v4 needed for Qt 5 typing
                ignored_modifiers = [
                    cast(Qt.KeyboardModifiers, Qt.KeyboardModifier.NoModifier),
                    cast(Qt.KeyboardModifiers, Qt.KeyboardModifier.ShiftModifier),
                ]
            else:
                ignored_modifiers = [
                    Qt.KeyboardModifier.NoModifier,
                    Qt.KeyboardModifier.ShiftModifier,
                ]
            has_modifier = event.modifiers() not in ignored_modifiers
            is_non_alnum = has_modifier or not event.text().strip()
            forward_unbound_keys = config.cache['input.forward_unbound_keys']
            key_info = keyutils.KeyInfo.from_event(event)
            should_filter_event = self._should_filter_event(key_info, parser)
            focus_widget = objects.qapp.focusWidget()
            log.modes.debug("match: {}, forward_unbound_keys: {}, "
                            "passthrough: {}, is_non_alnum: {}, "
                            "should_forward_event: {}, dry_run: {} "
                            "--> filter: {} (focused: {!r})".format(
                                match, forward_unbound_keys,
                                parser.passthrough, is_non_alnum,
                                should_filter_event, dry_run, filter_this,
                                qtutils.qobj_repr(focus_widget)))
        return filter_this

    def _handle_keyrelease(self, event: QKeyEvent) -> bool:
        """Handle filtering of KeyRelease events.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.
        """
        # handle like matching KeyPress
        keyevent = keyutils.KeyEvent.from_event(event)
        do_log = (self.mode in self.parsers) and \
            self.parsers[self.mode].get_do_log()
        if keyevent in self._releaseevents_to_pass:
            if do_log:
                log.modes.debug("Passing release event: {}".format(keyevent))
            self._releaseevents_to_pass.remove(keyevent)
            filter_this = False
        else:
            # Record the releases for partial matches to later forward along
            # with the presses
            for match_event in self._partial_match_events[::-1]:
                if match_event.add_event_release(event):
                    break
            filter_this = True
        if do_log:
            log.modes.debug("filter: {}".format(filter_this))
        return filter_this

    @staticmethod
    def _should_filter_event(key_info: keyutils.KeyInfo,
                             parser: basekeyparser.BaseKeyParser) -> bool:
        """Returns True if the event should be filtered, False otherwise."""
        if machinery.IS_QT5:  # FIXME:v4 needed for Qt 5 typing
            ignored_modifiers = [
                cast(Qt.KeyboardModifiers, Qt.KeyboardModifier.NoModifier),
                cast(Qt.KeyboardModifiers, Qt.KeyboardModifier.ShiftModifier),
            ]
        else:
            ignored_modifiers = [
                Qt.KeyboardModifier.NoModifier,
                Qt.KeyboardModifier.ShiftModifier,
            ]
        has_modifier = key_info.modifiers not in ignored_modifiers
        is_non_alnum = has_modifier or not key_info.text().strip()
        forward_unbound_keys = config.cache['input.forward_unbound_keys']
        return not (parser.passthrough or forward_unbound_keys == 'all' or
            (forward_unbound_keys == 'auto' and is_non_alnum))

    @pyqtSlot(usertypes.KeyMode, str)
    def forward_partial_match_event(self, mode: usertypes.KeyMode,  # noqa: C901
                                    text: str = None) -> None:
        """Forward the oldest partial match event for a given mode.

        Args:
            mode: The mode from which the forwarded match is.
            text: The expected text to be forwarded. Only used for debug
                  purposes. Default is None.
        """
        if mode not in self.parsers:
            raise ValueError("Can't forward partial key: No keyparser for "
                             "mode {}".format(mode))
        parser = self.parsers[mode]
        do_log = parser.get_do_log()
        if not self._partial_match_events:
            if parser.allow_forward:
                log.modes.warning("Attempting to forward for mode {} "
                                  "(expected text = {}), which should allow "
                                  "forwarding, but there are no events to "
                                  "forward.".format(mode, text))
            return
        match_event = self._partial_match_events.pop(0)
        if parser.allow_forward and (not
                self._should_filter_event(match_event.key_info_press, parser)):
            if do_log:
                log.modes.debug("Forwarding partial match event in mode "
                                "{}.".format(mode))
                text_actual = str(match_event.key_info_press)
                if (text is not None) and (text_actual != text):
                    log.modes.debug("Text mismatch (this is likely benign): "
                                    "'{}' != '{}'".format(text_actual, text))
            # Get the widget to which the event will be forwarded
            widget_name = parser.forward_widget_name
            if widget_name is None:
                # By default, the widget is the current widget of the browser
                tabbed_browser = objreg.get('tabbed-browser', scope='window',
                    window=self._win_id)
                tab = tabbed_browser.widget.currentWidget()
                if tab is None:
                    raise cmdutils.CommandError("No WebView available yet!")
                send_event = tab.send_event
            else:
                # When a specific widget is specified, QApplication.sendEvent
                # is used
                widget = objreg.get(widget_name, scope='window',
                    window=self._win_id)
                send_event = functools.partial(QApplication.sendEvent, widget)
            for event_ in match_event.to_events():
                if do_log:
                    log.modes.debug("Sending event {}".format(event_))
                send_event(event_)
            if not match_event.is_released():
                if do_log:
                    log.modes.debug("Adding release event for pass: "
                                    "{}".format(match_event.key_event))
                self._releaseevents_to_pass.add(match_event.key_event)

    @pyqtSlot(usertypes.KeyMode)
    def forward_all_partial_match_events(self, mode: usertypes.KeyMode, *,
                                         stop_timer: bool = False,
                                         is_timeout: bool = False) -> None:
        """Forward all partial match events for a given mode.

        Args:
            mode: The mode from which the forwarded match is.
            stop_timer: If true, stop the partial timer (and any nested timers)
                        as well. Default is False.
            is_timeout: True if this invocation is the result of a timeout.
        """
        do_log = (mode in self.parsers) and self.parsers[mode].get_do_log()
        if do_log:
            log.modes.debug(f"Forwarding all partial matches ({is_timeout=}).")
        if stop_timer:
            if do_log:
                log.modes.debug("Stopping partial timer.")
            self._stop_partial_timer()
        if mode in self.parsers:
            parser = self.parsers[mode]
            if isinstance(parser, modeparsers.HintKeyParser):
                # Call the subparsers analogous function, propagating the timer
                # stopping.
                parser.forward_all_partial_match_events(stop_timer=True)
        if self._partial_match_events:
            while self._partial_match_events:
                self.forward_partial_match_event(mode)
            # If mode wasn't in self.parsers, one of the
            # self.forward_partial_match_event calls (of which we have at least
            # one) would have raised an error, so it is safe to assert
            assert mode in self.parsers
            self.parsers[mode].clear_keystring()

    @pyqtSlot()
    def clear_partial_match_events(self) -> None:
        self._partial_match_events = []

    def _start_partial_timer(self) -> None:
        """Set a timeout to clear a partial keystring."""
        timeout = config.val.input.partial_timeout
        if self.parsers[self.mode].allow_partial_timeout and (timeout != 0):
            self._partial_timer.setInterval(timeout)
            # Disconnect existing connections (if any)
            try:
                self._partial_timer.timeout.disconnect()
            except TypeError:
                pass
            self._partial_timer.timeout.connect(functools.partial(
                self.forward_all_partial_match_events, self.mode,
                is_timeout=True))
            self._partial_timer.start()

    def _stop_partial_timer(self) -> None:
        """Prematurely stop the the partial keystring timer."""
        self._partial_timer.stop()

    def register(self, mode: usertypes.KeyMode,
                 parser: basekeyparser.BaseKeyParser) -> None:
        """Register a new mode."""
        assert parser is not None
        self.parsers[mode] = parser
        parser.request_leave.connect(self.leave)
        parser.keystring_updated.connect(
            functools.partial(self.keystring_updated.emit, mode))
        parser.forward_partial_key.connect(
            functools.partial(self.forward_partial_key.emit, mode))
        parser.clear_partial_keys.connect(self.clear_partial_match_events)

    def enter(self, mode: usertypes.KeyMode,
              reason: str = None,
              only_if_normal: bool = False) -> None:
        """Enter a new mode.

        Args:
            mode: The mode to enter as a KeyMode member.
            reason: Why the mode was entered.
            only_if_normal: Only enter the new mode if we're in normal mode.
        """
        if mode == usertypes.KeyMode.normal:
            self.leave(self.mode, reason='enter normal: {}'.format(reason))
            return

        log.modes.debug("Entering mode {}{}".format(
            mode, '' if reason is None else ' (reason: {})'.format(reason)))
        if mode not in self.parsers:
            raise ValueError("No keyparser for mode {}".format(mode))
        if self.mode == mode or (self.mode in PROMPT_MODES and
                                 mode in PROMPT_MODES):
            log.modes.debug("Ignoring request as we're in mode {} "
                            "already.".format(self.mode))
            return
        if self.mode != usertypes.KeyMode.normal:
            if only_if_normal:
                log.modes.debug("Ignoring request as we're in mode {} "
                                "and only_if_normal is set..".format(
                                    self.mode))
                return
            log.modes.debug("Overriding mode {}.".format(self.mode))
            self.left.emit(self.mode, mode, self._win_id)

        if mode in PROMPT_MODES and self.mode in INPUT_MODES:
            self._prev_mode = self.mode
        else:
            self._prev_mode = usertypes.KeyMode.normal

        self.change_mode(mode)
        self.entered.emit(mode, self._win_id)

    @cmdutils.register(instance='mode-manager', scope='window')
    def mode_enter(self, mode: str) -> None:
        """Enter a key mode.

        Args:
            mode: The mode to enter. See `:help bindings.commands` for the
                  available modes, but note that hint/command/yesno/prompt mode
                  can't be entered manually.
        """
        try:
            m = usertypes.KeyMode[mode]
        except KeyError:
            raise cmdutils.CommandError("Mode {} does not exist!".format(mode))

        if m in [usertypes.KeyMode.hint, usertypes.KeyMode.command,
                 usertypes.KeyMode.yesno, usertypes.KeyMode.prompt,
                 usertypes.KeyMode.register]:
            raise cmdutils.CommandError(
                "Mode {} can't be entered manually!".format(mode))

        self.enter(m, 'command')

    @pyqtSlot(usertypes.KeyMode, str, bool)
    def leave(self, mode: usertypes.KeyMode,
              reason: str = None,
              maybe: bool = False) -> None:
        """Leave a key mode.

        Args:
            mode: The mode to leave as a usertypes.KeyMode member.
            reason: Why the mode was left.
            maybe: If set, ignore the request if we're not in that mode.
        """
        if self.mode != mode:
            if maybe:
                log.modes.debug("Ignoring leave request for {} (reason {}) as "
                                "we're in mode {}".format(
                                    mode, reason, self.mode))
                return
            else:
                raise NotInModeError("Not in mode {}!".format(mode))

        log.modes.debug("Leaving mode {}{}".format(
            mode, '' if reason is None else ' (reason: {})'.format(reason)))
        # leaving a mode implies clearing keychain, see
        # https://github.com/qutebrowser/qutebrowser/issues/1805
        self.clear_keychain()
        self.change_mode(usertypes.KeyMode.normal)
        self.left.emit(mode, self.mode, self._win_id)
        if mode in PROMPT_MODES:
            self.enter(self._prev_mode,
                       reason='restore mode before {}'.format(mode.name))

    @cmdutils.register(instance='mode-manager',
                       not_modes=[usertypes.KeyMode.normal], scope='window')
    def mode_leave(self) -> None:
        """Leave the mode we're currently in."""
        if self.mode == usertypes.KeyMode.normal:
            raise ValueError("Can't leave normal mode!")
        self.leave(self.mode, 'leave current')

    def change_mode(self, mode: usertypes.KeyMode) -> None:
        """Changes mode and forwards partial match events if present."""
        # catches the case where change of mode is not keys, e.g. mouse click
        self.forward_all_partial_match_events(self.mode, stop_timer=True)
        self.mode = mode

    def handle_event(self, event: QEvent) -> bool:
        """Filter all events based on the currently set mode.

        Also calls the real keypress handler.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.
        """
        handlers: Mapping[QEvent.Type, Callable[[QKeyEvent], bool]] = {
            QEvent.Type.KeyPress: self._handle_keypress,
            QEvent.Type.KeyRelease: self._handle_keyrelease,
            QEvent.Type.ShortcutOverride:
                functools.partial(self._handle_keypress, dry_run=True),
        }
        handler = handlers[event.type()]
        return handler(cast(QKeyEvent, event))

    @cmdutils.register(instance='mode-manager', scope='window')
    def clear_keychain(self) -> None:
        """Clear the currently entered key chain."""
        self.parsers[self.mode].clear_keystring()
