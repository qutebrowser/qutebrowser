# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""The commandline in the statusbar."""

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QUrl
from PyQt5.QtWidgets import QSizePolicy

from qutebrowser.keyinput import modeman, modeparsers
from qutebrowser.commands import runners, cmdexc, cmdutils
from qutebrowser.widgets import misc
from qutebrowser.models import cmdhistory
from qutebrowser.utils import usertypes, log, objreg


class Command(misc.MinimalLineEditMixin, misc.CommandLineEdit):

    """The commandline part of the statusbar.

    Attributes:
        _cursor_part: The part the cursor is currently over.
        _win_id: The window ID this widget is associated with.

    Signals:
        got_cmd: Emitted when a command is triggered by the user.
                 arg: The command string.
        got_search: Emitted when the user started a new search.
                    arg: The search term.
        got_rev_search: Emitted when the user started a new reverse search.
                        arg: The search term.
        clear_completion_selection: Emitted before the completion widget is
                                    hidden.
        hide_completion: Emitted when the completion widget should be hidden.
        update_completion: Emitted when the completion should be shown/updated.
                           arg 0: The prefix used.
                           arg 1: A list of strings (commandline separated into
                           parts)
                           arg 2: The part the cursor is currently in.
        show_cmd: Emitted when command input should be shown.
        hide_cmd: Emitted when command input can be hidden.
    """

    got_cmd = pyqtSignal(str)
    got_search = pyqtSignal(str)
    got_search_rev = pyqtSignal(str)
    clear_completion_selection = pyqtSignal()
    hide_completion = pyqtSignal()
    update_completion = pyqtSignal(str, list, int)
    show_cmd = pyqtSignal()
    hide_cmd = pyqtSignal()

    def __init__(self, win_id, parent=None):
        misc.CommandLineEdit.__init__(self, parent)
        misc.MinimalLineEditMixin.__init__(self)
        self._win_id = win_id
        self._cursor_part = 0
        self.history.history = objreg.get('command-history').data
        self._empty_item_idx = None
        self.textEdited.connect(self.on_text_edited)
        self.cursorPositionChanged.connect(self._update_cursor_part)
        self.cursorPositionChanged.connect(self.on_cursor_position_changed)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)

    def prefix(self):
        """Get the currently entered command prefix."""
        text = self.text()
        if not text:
            return ''
        elif text[0] in modeparsers.STARTCHARS:
            return text[0]
        else:
            return ''

    def split(self, keep=False):
        """Get the text split up in parts.

        Args:
            keep: Whether to keep special chars and whitespace.
        """
        text = self.text()[len(self.prefix()):]
        if not text:
            # When only ":" is entered, we already have one imaginary part,
            # which just is empty at the moment.
            return ['']
        if not text.strip():
            # Text is only whitespace so we treat this as a single element with
            # the whitespace.
            return [text]
        runner = runners.CommandRunner(self._win_id)
        parts = runner.parse(text, fallback=True, alias_no_args=False,
                             keep=keep)
        if self._empty_item_idx is not None:
            log.completion.debug("Empty element queued at {}, "
                                 "inserting.".format(self._empty_item_idx))
            parts.insert(self._empty_item_idx, '')
        #log.completion.debug("Splitting '{}' -> {}".format(text, parts))
        return parts

    @pyqtSlot()
    def _update_cursor_part(self):
        """Get the part index of the commandline where the cursor is over."""
        cursor_pos = self.cursorPosition()
        snippet = slice(cursor_pos - 1, cursor_pos + 1)
        if self.text()[snippet] == '  ':
            spaces = True
        else:
            spaces = False
        cursor_pos -= len(self.prefix())
        parts = self.split(keep=True)
        log.completion.vdebug(
            "text: {}, parts: {}, cursor_pos after removing prefix '{}': "
            "{}".format(self.text(), parts, self.prefix(), cursor_pos))
        for i, part in enumerate(parts):
            log.completion.vdebug("Checking part {}: {}".format(i, parts[i]))
            if cursor_pos <= len(part):
                # foo| bar
                self._cursor_part = i
                if spaces:
                    self._empty_item_idx = i
                else:
                    self._empty_item_idx = None
                log.completion.vdebug("cursor_pos {} <= len(part) {}, "
                                      "setting cursor_part {}, empty_item_idx "
                                      "{}".format(cursor_pos, len(part), i,
                                                  self._empty_item_idx))
                break
            cursor_pos -= len(part)
            log.completion.vdebug(
                "Removing len({!r}) -> {} from cursor_pos -> {}".format(
                    part, len(part), cursor_pos))
        log.completion.debug("cursor_part {}, spaces {}".format(
            self._cursor_part, spaces))
        return

    @pyqtSlot()
    def on_cursor_position_changed(self):
        """Update completion when the cursor position changed."""
        self.update_completion.emit(self.prefix(), self.split(),
                                    self._cursor_part)

    @pyqtSlot(str)
    def set_cmd_text(self, text):
        """Preset the statusbar to some text.

        Args:
            text: The text to set as string.
        """
        old_text = self.text()
        self.setText(text)
        if old_text != text and len(old_text) == len(text):
            # We want the completion to pop out here, but the cursor position
            # won't change, so we make sure we emit update_completion.
            self.update_completion.emit(self.prefix(), self.split(),
                                        self._cursor_part)
        log.modes.debug("Setting command text, focusing {!r}".format(self))
        self.setFocus()
        self.show_cmd.emit()

    @cmdutils.register(instance='status-command', name='set-cmd-text',
                       scope='window')
    def set_cmd_text_command(self, text):
        """Preset the statusbar to some text.

        //

        Wrapper for set_cmd_text to check the arguments and allow multiple
        strings which will get joined.

        Args:
            text: The commandline to set.
        """
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        if '{url}' in text:
            url = tabbed_browser.current_url().toString(
                QUrl.FullyEncoded | QUrl.RemovePassword)
            # FIXME we currently replace the URL in any place in the arguments,
            # rather than just replacing it if it is a dedicated argument. We
            # could split the args, but then trailing spaces would be lost, so
            # I'm not sure what's the best thing to do here
            # https://github.com/The-Compiler/qutebrowser/issues/123
            text = text.replace('{url}', url)
        if not text[0] in modeparsers.STARTCHARS:
            raise cmdexc.CommandError(
                "Invalid command text '{}'.".format(text))
        self.set_cmd_text(text)

    @pyqtSlot(str, bool)
    def on_change_completed_part(self, newtext, immediate):
        """Change the part we're currently completing in the commandline.

        Args:
            text: The text to set (string).
            immediate: True if the text should be completed immediately
                       including a trailing space and we shouldn't continue
                       completing the current item.
        """
        parts = self.split(keep=True)
        log.completion.debug("changing part {} to '{}'".format(
            self._cursor_part, newtext))
        parts[self._cursor_part] = newtext
        # We want to place the cursor directly after the part we just changed.
        cursor_str = self.prefix() + ' '.join(parts[:self._cursor_part + 1])
        if immediate:
            # If we should complete immediately, we want to move the cursor by
            # one more char, to get to the next field.
            cursor_str += ' '
        text = self.prefix() + ''.join(parts)
        if immediate and self._cursor_part == len(parts) - 1:
            # If we should complete immediately and we're completing the last
            # part in the commandline, we automatically add a space.
            text += ' '
        self.setText(text)
        log.completion.debug("Placing cursor after '{}'".format(cursor_str))
        log.modes.debug("Completion triggered, focusing {!r}".format(self))
        self.setCursorPosition(len(cursor_str))
        self.setFocus()
        self.show_cmd.emit()

    @cmdutils.register(instance='status-command', hide=True,
                       modes=[usertypes.KeyMode.command], scope='window')
    def command_history_prev(self):
        """Go back in the commandline history."""
        try:
            if not self.history.is_browsing():
                item = self.history.start(self.text().strip())
            else:
                item = self.history.previtem()
        except (cmdhistory.HistoryEmptyError,
                cmdhistory.HistoryEndReachedError):
            return
        if item:
            self.set_cmd_text(item)

    @cmdutils.register(instance='status-command', hide=True,
                       modes=[usertypes.KeyMode.command], scope='window')
    def command_history_next(self):
        """Go forward in the commandline history."""
        if not self.history.is_browsing():
            return
        try:
            item = self.history.nextitem()
        except cmdhistory.HistoryEndReachedError:
            return
        if item:
            self.set_cmd_text(item)

    @cmdutils.register(instance='status-command', hide=True,
                       modes=[usertypes.KeyMode.command], scope='window')
    def command_accept(self):
        """Execute the command currently in the commandline."""
        signals = {
            ':': self.got_cmd,
            '/': self.got_search,
            '?': self.got_search_rev,
        }
        text = self.text()
        self.history.append(text)
        modeman.leave(self._win_id, usertypes.KeyMode.command, 'cmd accept')
        if text[0] in signals:
            signals[text[0]].emit(text.lstrip(text[0]))

    @pyqtSlot(str)
    def on_text_edited(self, _text):
        """Slot for textEdited. Stop history and update completion."""
        self.history.stop()
        self._empty_item_idx = None
        # We also want to update the cursor part and emit update_completion
        # here, but that's already done for us by cursorPositionChanged
        # anyways, so we don't need to do it twice.

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Clear up when ommand mode was left.

        - Clear the statusbar text if it's explicitely unfocused.
        - Clear completion selection
        - Hide completion

        Args:
            mode: The mode which was left.
        """
        if mode == usertypes.KeyMode.command:
            self.setText('')
            self.history.stop()
            self.hide_cmd.emit()
            self.clear_completion_selection.emit()
            self.hide_completion.emit()

    def focusInEvent(self, e):
        """Extend focusInEvent to enter command mode."""
        modeman.maybe_enter(self._win_id, usertypes.KeyMode.command,
                            'cmd focus')
        super().focusInEvent(e)

    def setText(self, text):
        """Extend setText to set prefix and make sure the prompt is ok."""
        if not text:
            pass
        elif text[0] in modeparsers.STARTCHARS:
            super().set_prompt(text[0])
        else:
            raise AssertionError("setText got called with invalid text "
                                 "'{}'!".format(text))
        super().setText(text)

    def keyPressEvent(self, e):
        """Override keyPressEvent to ignore Return key presses.

        If this widget is focused, we are in passthrough key mode, and
        Enter/Shift+Enter/etc. will cause QLineEdit to think it's finished
        without command_accept to be called.
        """
        if e.key() == Qt.Key_Return:
            e.ignore()
            return
        else:
            super().keyPressEvent(e)
