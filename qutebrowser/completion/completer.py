# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Completer attached to a CompletionView."""

import attr
from PyQt5.QtCore import pyqtSlot, QObject, QTimer

from qutebrowser.config import config
from qutebrowser.commands import runners
from qutebrowser.misc import objects
from qutebrowser.utils import log, utils, debug
from qutebrowser.completion.models import miscmodels


@attr.s
class CompletionInfo:

    """Context passed into all completion functions."""

    config = attr.ib()
    keyconf = attr.ib()
    win_id = attr.ib()


class Completer(QObject):

    """Completer which manages completions in a CompletionView.

    Attributes:
        _cmd: The statusbar Command object this completer belongs to.
        _win_id: The id of the window that owns this object.
        _timer: The timer used to trigger the completion update.
        _last_cursor_pos: The old cursor position so we avoid double completion
                          updates.
        _last_text: The old command text so we avoid double completion updates.
        _last_before_cursor: The prior value of before_cursor.
    """

    def __init__(self, *, cmd, win_id, parent=None):
        super().__init__(parent)
        self._cmd = cmd
        self._win_id = win_id
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._update_completion)
        self._last_cursor_pos = -1
        self._last_text = None
        self._last_before_cursor = None
        self._cmd.update_completion.connect(self.schedule_completion_update)

    def __repr__(self):
        return utils.get_repr(self)

    def _model(self):
        """Convenience method to get the current completion model."""
        completion = self.parent()
        return completion.model()

    def _get_new_completion(self, before_cursor, under_cursor):
        """Get the completion function based on the current command text.

        Args:
            before_cursor: The command chunks before the cursor.
            under_cursor: The command chunk under the cursor.

        Return:
            A completion model.
        """
        if '--' in before_cursor or under_cursor.startswith('-'):
            # cursor on a flag or after an explicit split (--)
            return None
        log.completion.debug("Before removing flags: {}".format(before_cursor))
        if not before_cursor:
            # '|' or 'set|'
            log.completion.debug('Starting command completion')
            return miscmodels.command
        try:
            cmd = objects.commands[before_cursor[0]]
        except KeyError:
            log.completion.debug("No completion for unknown command: {}"
                                 .format(before_cursor[0]))
            return None

        before_cursor = [x for x in before_cursor if not x.startswith('-')]
        log.completion.debug("After removing flags: {}".format(before_cursor))
        argpos = len(before_cursor) - 1
        try:
            func = cmd.get_pos_arg_info(argpos).completion
        except IndexError:
            log.completion.debug("No completion in position {}".format(argpos))
            return None
        return func

    def _quote(self, s):
        """Quote s if it needs quoting for the commandline.

        Note we don't use shlex.quote because that quotes a lot of shell
        metachars we don't need to have quoted.
        """
        if not s:
            return "''"
        elif any(c in s for c in ' "\'\t\n\\'):
            # use single quotes, and put single quotes into double quotes
            # the string $'b is then quoted as '$'"'"'b'
            return "'" + s.replace("'", "'\"'\"'") + "'"
        else:
            return s

    def _partition(self):
        """Divide the commandline text into chunks around the cursor position.

        Return:
            ([parts_before_cursor], 'part_under_cursor', [parts_after_cursor])
        """
        text = self._cmd.text()[len(self._cmd.prefix()):]
        if not text or not text.strip():
            # Only ":", empty part under the cursor with nothing before/after
            return [], '', []
        parser = runners.CommandParser()
        result = parser.parse(text, fallback=True, keep=True)
        parts = [x for x in result.cmdline if x]
        pos = self._cmd.cursorPosition() - len(self._cmd.prefix())
        pos = min(pos, len(text))  # Qt treats 2-byte UTF-16 chars as 2 chars
        log.completion.debug('partitioning {} around position {}'.format(parts,
                                                                         pos))
        for i, part in enumerate(parts):
            pos -= len(part)
            if pos <= 0:
                if part[pos-1:pos+1].isspace():
                    # cursor is in a space between two existing words
                    parts.insert(i, '')
                prefix = [x.strip() for x in parts[:i]]
                center = parts[i].strip()
                # strip trailing whitepsace included as a separate token
                postfix = [x.strip() for x in parts[i+1:] if not x.isspace()]
                log.completion.debug(
                    "partitioned: {} '{}' {}".format(prefix, center, postfix))
                return prefix, center, postfix

        raise utils.Unreachable("Not all parts consumed: {}".format(parts))

    @pyqtSlot(str)
    def on_selection_changed(self, text):
        """Change the completed part if a new item was selected.

        Called from the views selectionChanged method.

        Args:
            text: Newly selected text.
        """
        if text is None:
            return
        before, center, after = self._partition()
        log.completion.debug("Changing {} to '{}'".format(center, text))
        try:
            maxsplit = objects.commands[before[0]].maxsplit
        except (KeyError, IndexError):
            maxsplit = None
        if maxsplit is None:
            text = self._quote(text)
        model = self._model()
        if model.count() == 1 and config.val.completion.quick:
            # If we only have one item, we want to apply it immediately and go
            # on to the next part, unless we are quick-completing the part
            # after maxsplit, so that we don't keep offering completions
            # (see issue #1519)
            if maxsplit is not None and maxsplit < len(before):
                self._change_completed_part(text, before, after)
            else:
                self._change_completed_part(text, before, after,
                                            immediate=True)
        else:
            self._change_completed_part(text, before, after)

    @pyqtSlot()
    def schedule_completion_update(self):
        """Schedule updating/enabling completion.

        For performance reasons we don't want to block here, instead we do this
        in the background.

        We delay the update only if we've already input some text and ignore
        updates if the text is shorter than completion.min_chars (unless we're
        hitting backspace in which case updates won't be ignored).
        """
        _cmd, _sep, rest = self._cmd.text().partition(' ')
        input_length = len(rest)
        if (0 < input_length < config.val.completion.min_chars and
                self._cmd.cursorPosition() > self._last_cursor_pos):
            log.completion.debug("Ignoring update because the length of "
                                 "the text is less than completion.min_chars.")
        elif (self._cmd.cursorPosition() == self._last_cursor_pos and
              self._cmd.text() == self._last_text):
            log.completion.debug("Ignoring update because there were no "
                                 "changes.")
        else:
            log.completion.debug("Scheduling completion update.")
            start_delay = config.val.completion.delay if self._last_text else 0
            self._timer.start(start_delay)
        self._last_cursor_pos = self._cmd.cursorPosition()
        self._last_text = self._cmd.text()

    @pyqtSlot()
    def _update_completion(self):
        """Check if completions are available and activate them."""
        completion = self.parent()

        if self._cmd.prefix() != ':':
            # This is a search or gibberish, so we don't need to complete
            # anything (yet)
            # FIXME complete searches
            # https://github.com/qutebrowser/qutebrowser/issues/32
            completion.set_model(None)
            self._last_before_cursor = None
            return

        before_cursor, pattern, after_cursor = self._partition()

        log.completion.debug("Updating completion: {} {} {}".format(
            before_cursor, pattern, after_cursor))

        pattern = pattern.strip("'\"")
        func = self._get_new_completion(before_cursor, pattern)

        if func is None:
            log.completion.debug('Clearing completion')
            completion.set_model(None)
            self._last_before_cursor = None
            return

        if before_cursor != self._last_before_cursor:
            self._last_before_cursor = before_cursor
            args = (x for x in before_cursor[1:] if not x.startswith('-'))
            with debug.log_time(log.completion, 'Starting {} completion'
                                .format(func.__name__)):
                info = CompletionInfo(config=config.instance,
                                      keyconf=config.key_instance,
                                      win_id=self._win_id)
                model = func(*args, info=info)
            with debug.log_time(log.completion, 'Set completion model'):
                completion.set_model(model)

        completion.set_pattern(pattern)

    def _change_completed_part(self, newtext, before, after, immediate=False):
        """Change the part we're currently completing in the commandline.

        Args:
            text: The text to set (string) for the token under the cursor.
            before: Commandline tokens before the token under the cursor.
            after: Commandline tokens after the token under the cursor.
            immediate: True if the text should be completed immediately
                       including a trailing space and we shouldn't continue
                       completing the current item.
        """
        text = self._cmd.prefix() + ' '.join(before + [newtext])
        pos = len(text) + (1 if immediate else 0)
        if after:
            text += ' ' + ' '.join(after)
        elif immediate:
            # pad with a space if quick-completing the last entry
            text += ' '
        log.completion.debug("setting text = '{}', pos = {}".format(text, pos))

        # generally, we don't want to let self._cmd emit cursorPositionChanged,
        # because that'll schedule a completion update. That happens when
        # tabbing through the completions, and we want to change the command
        # text but we also want to keep the original completion list for the
        # command the user manually entered. The exception is when we're
        # immediately completing, in which case we *do* want to update the
        # completion view so that we can start completing the next part
        if not immediate:
            self._cmd.blockSignals(True)

        self._cmd.setText(text)
        self._cmd.setCursorPosition(pos)
        self._cmd.setFocus()

        self._cmd.blockSignals(False)
        self._cmd.show_cmd.emit()
