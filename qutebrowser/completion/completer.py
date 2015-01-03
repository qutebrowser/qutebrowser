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

"""Completer attached to a CompletionView."""

from PyQt5.QtCore import pyqtSlot, QObject, QTimer

from qutebrowser.config import config, configdata
from qutebrowser.commands import cmdutils, runners
from qutebrowser.utils import usertypes, log, objreg, utils
from qutebrowser.completion.models import completion as models
from qutebrowser.completion.models.sortfilter import (
    CompletionFilterModel as CFM)


class Completer(QObject):

    """Completer which manages completions in a CompletionView.

    Attributes:
        models: dict of available completion models.
        _cmd: The statusbar Command object this completer belongs to.
        _ignore_change: Whether to ignore the next completion update.
        _win_id: The window ID this completer is in.
        _timer: The timer used to trigger the completion update.
        _cursor_part: The cursor part index for the next completion update.
        _last_cursor_pos: The old cursor position so we avoid double completion
                          updates.
        _last_text: The old command text so we avoid double completion updates.
    """

    def __init__(self, cmd, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self._cmd = cmd
        self._cmd.update_completion.connect(self.schedule_completion_update)
        self._cmd.textEdited.connect(self.on_text_edited)
        self._ignore_change = False
        self._empty_item_idx = None

        self._models = {
            usertypes.Completion.option: {},
            usertypes.Completion.value: {},
        }
        self._init_static_completions()
        self._init_setting_completions()
        self.init_quickmark_completions()
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self.update_completion)
        self._cursor_part = None
        self._last_cursor_pos = None
        self._last_text = None

    def __repr__(self):
        return utils.get_repr(self)

    def _model(self):
        """Convienience method to get the current completion model."""
        completion = objreg.get('completion', scope='window',
                                window=self._win_id)
        return completion.model()

    def _init_static_completions(self):
        """Initialize the static completion models."""
        self._models[usertypes.Completion.command] = CFM(
            models.CommandCompletionModel(self), self)
        self._models[usertypes.Completion.helptopic] = CFM(
            models.HelpCompletionModel(self), self)

    def _init_setting_completions(self):
        """Initialize setting completion models."""
        self._models[usertypes.Completion.section] = CFM(
            models.SettingSectionCompletionModel(self), self)
        self._models[usertypes.Completion.option] = {}
        self._models[usertypes.Completion.value] = {}
        for sectname in configdata.DATA:
            model = models.SettingOptionCompletionModel(sectname, self)
            self._models[usertypes.Completion.option][sectname] = CFM(
                model, self)
            self._models[usertypes.Completion.value][sectname] = {}
            for opt in configdata.DATA[sectname].keys():
                model = models.SettingValueCompletionModel(sectname, opt, self)
                self._models[usertypes.Completion.value][sectname][opt] = CFM(
                    model, self)

    @pyqtSlot()
    def init_quickmark_completions(self):
        """Initialize quickmark completion models."""
        try:
            self._models[usertypes.Completion.quickmark_by_url].deleteLater()
            self._models[usertypes.Completion.quickmark_by_name].deleteLater()
        except KeyError:
            pass
        self._models[usertypes.Completion.quickmark_by_url] = CFM(
            models.QuickmarkCompletionModel('url', self), self)
        self._models[usertypes.Completion.quickmark_by_name] = CFM(
            models.QuickmarkCompletionModel('name', self), self)

    def _get_completion_model(self, completion, parts, cursor_part):
        """Get a completion model based on an enum member.

        Args:
            completion: An usertypes.Completion member.
            parts: The parts currently in the commandline.
            cursor_part: The part the cursor is in.

        Return:
            A completion model.
        """
        if completion == usertypes.Completion.option:
            section = parts[cursor_part - 1]
            model = self._models[completion].get(section)
        elif completion == usertypes.Completion.value:
            section = parts[cursor_part - 2]
            option = parts[cursor_part - 1]
            try:
                model = self._models[completion][section][option]
            except KeyError:
                # No completion model for this section/option.
                model = None
        else:
            model = self._models.get(completion)
        return model

    def _filter_cmdline_parts(self, parts, cursor_part):
        """Filter a list of commandline parts to exclude flags.

        Args:
            parts: A list of parts.
            cursor_part: The index of the part the cursor is over.

        Return:
            A (parts, cursor_part) tuple with the modified values.
        """
        if parts == ['']:
            # Empty commandline, i.e. only :.
            return [''], 0
        filtered_parts = []
        for i, part in enumerate(parts):
            if part == '--':
                break
            elif part.startswith('-'):
                if cursor_part >= i:
                    cursor_part -= 1
            else:
                filtered_parts.append(part)
        return filtered_parts, cursor_part

    def _get_new_completion(self, parts, cursor_part):
        """Get a new completion.

        Args:
            parts: The command chunks to get a completion for.
            cursor_part: The part the cursor is over currently.

        Return:
            A completion model.
        """
        try:
            if parts[cursor_part].startswith('-'):
                # cursor on a flag
                return
        except IndexError:
            pass
        log.completion.debug("Before filtering flags: parts {}, cursor_part "
                             "{}".format(parts, cursor_part))
        parts, cursor_part = self._filter_cmdline_parts(parts, cursor_part)
        log.completion.debug("After filtering flags: parts {}, cursor_part "
                             "{}".format(parts, cursor_part))
        if cursor_part == 0:
            # '|' or 'set|'
            return self._models[usertypes.Completion.command]
        # delegate completion to command
        try:
            completions = cmdutils.cmd_dict[parts[0]].completion
        except KeyError:
            # entering an unknown command
            return None
        if completions is None:
            # command without any available completions
            return None
        dbg_completions = [c.name for c in completions]
        try:
            idx = cursor_part - 1
            completion = completions[idx]
        except IndexError:
            # More arguments than completions
            log.completion.debug("completions: {}".format(
                ', '.join(dbg_completions)))
            return None
        dbg_completions[idx] = '*' + dbg_completions[idx] + '*'
        log.completion.debug("completions: {}".format(
            ', '.join(dbg_completions)))
        model = self._get_completion_model(completion, parts, cursor_part)
        return model

    def _quote(self, s):
        """Quote s if it needs quoting for the commandline.

        Note we don't use shlex.quote because that quotes a lot of shell
        metachars we don't need to have quoted.
        """
        if not s:
            return "''"
        elif any(c in s for c in ' \'\t\n\\'):
            # use single quotes, and put single quotes into double quotes
            # the string $'b is then quoted as '$'"'"'b'
            return "'" + s.replace("'", "'\"'\"'") + "'"
        else:
            return s

    def selection_changed(self, selected, _deselected):
        """Change the completed part if a new item was selected.

        Called from the views selectionChanged method.

        Args:
            selected: New selection.
            _delected: Previous selection.
        """
        indexes = selected.indexes()
        if not indexes:
            return
        model = self._model()
        data = model.data(indexes[0])
        if data is None:
            return
        data = self._quote(data)
        if model.count() == 1 and config.get('completion', 'quick-complete'):
            # If we only have one item, we want to apply it immediately
            # and go on to the next part.
            self.change_completed_part(data, immediate=True)
        else:
            log.completion.debug("Will ignore next completion update.")
            self._ignore_change = True
            self.change_completed_part(data)

    @pyqtSlot()
    def schedule_completion_update(self):
        """Schedule updating/enabling completion.

        For performance reasons we don't want to block here, instead we do this
        in the background.
        """
        if (self._cmd.cursorPosition() == self._last_cursor_pos and
                self._cmd.text() == self._last_text):
            log.completion.debug("Ignoring update because there were no "
                                 "changes.")
        else:
            log.completion.debug("Scheduling completion update.")
            self._timer.start()
        self._last_cursor_pos = self._cmd.cursorPosition()
        self._last_text = self._cmd.text()

    @pyqtSlot()
    def update_completion(self):
        """Check if completions are available and activate them."""
        self.update_cursor_part()
        parts = self.split()

        log.completion.debug(
            "Updating completion - prefix {}, parts {}, cursor_part {}".format(
                self._cmd.prefix(), parts, self._cursor_part))

        if self._ignore_change:
            log.completion.debug("Ignoring completion update because "
                                 "ignore_change is True.")
            self._ignore_change = False
            return

        completion = objreg.get('completion', scope='window',
                                window=self._win_id)

        if self._cmd.prefix() != ':':
            # This is a search or gibberish, so we don't need to complete
            # anything (yet)
            # FIXME complete searchs
            # https://github.com/The-Compiler/qutebrowser/issues/32
            completion.hide()
            return

        model = self._get_new_completion(parts, self._cursor_part)

        if model != self._model():
            if model is None:
                completion.hide()
            else:
                completion.set_model(model)

        if model is None:
            log.completion.debug("No completion model for {}.".format(parts))
            return

        try:
            pattern = parts[self._cursor_part].strip()
        except IndexError:
            pattern = ''
        self._model().set_pattern(pattern)

        log.completion.debug(
            "New completion for {}: {}, with pattern '{}'".format(
                parts, model.srcmodel.__class__.__name__, pattern))

        if self._model().count() == 0:
            completion.hide()
            return

        if completion.enabled:
            completion.show()

    def split(self, keep=False, aliases=False):
        """Get the text split up in parts.

        Args:
            keep: Whether to keep special chars and whitespace.
            aliases: Whether to resolve aliases.
        """
        text = self._cmd.text()[len(self._cmd.prefix()):]
        if not text:
            # When only ":" is entered, we already have one imaginary part,
            # which just is empty at the moment.
            return ['']
        if not text.strip():
            # Text is only whitespace so we treat this as a single element with
            # the whitespace.
            return [text]
        runner = runners.CommandRunner(self._win_id)
        parts = runner.parse(text, fallback=True, aliases=aliases, keep=keep)
        if self._empty_item_idx is not None:
            log.completion.debug("Empty element queued at {}, "
                                 "inserting.".format(self._empty_item_idx))
            parts.insert(self._empty_item_idx, '')
        #log.completion.debug("Splitting '{}' -> {}".format(text, parts))
        return parts

    @pyqtSlot()
    def update_cursor_part(self):
        """Get the part index of the commandline where the cursor is over."""
        cursor_pos = self._cmd.cursorPosition()
        snippet = slice(cursor_pos - 1, cursor_pos + 1)
        if self._cmd.text()[snippet] == '  ':
            spaces = True
        else:
            spaces = False
        cursor_pos -= len(self._cmd.prefix())
        parts = self.split(keep=True)
        log.completion.vdebug(
            "text: {}, parts: {}, cursor_pos after removing prefix '{}': "
            "{}".format(self._cmd.text(), parts, self._cmd.prefix(),
                        cursor_pos))
        skip = 0
        for i, part in enumerate(parts):
            log.completion.vdebug("Checking part {}: {}".format(i, parts[i]))
            if not part:
                skip += 1
                continue
            if cursor_pos <= len(part):
                # foo| bar
                self._cursor_part = i - skip
                if spaces:
                    self._empty_item_idx = i - skip
                else:
                    self._empty_item_idx = None
                log.completion.vdebug("cursor_pos {} <= len(part) {}, "
                                      "setting cursor_part {} - {} (skip), "
                                      "empty_item_idx {}".format(
                                          cursor_pos, len(part), i, skip,
                                          self._empty_item_idx))
                break
            cursor_pos -= len(part)
            log.completion.vdebug(
                "Removing len({!r}) -> {} from cursor_pos -> {}".format(
                    part, len(part), cursor_pos))
        else:
            self._cursor_part = i - skip
            if spaces:
                self._empty_item_idx = i - skip
            else:
                self._empty_item_idx = None
        log.completion.debug("cursor_part {}, spaces {}".format(
            self._cursor_part, spaces))
        return

    def change_completed_part(self, newtext, immediate=False):
        """Change the part we're currently completing in the commandline.

        Args:
            text: The text to set (string).
            immediate: True if the text should be completed immediately
                       including a trailing space and we shouldn't continue
                       completing the current item.
        """
        parts = self.split()
        log.completion.debug("changing part {} to '{}'".format(
            self._cursor_part, newtext))
        try:
            parts[self._cursor_part] = newtext
        except IndexError:
            parts.append(newtext)
        # We want to place the cursor directly after the part we just changed.
        cursor_str = self._cmd.prefix() + ' '.join(
            parts[:self._cursor_part + 1])
        if immediate:
            # If we should complete immediately, we want to move the cursor by
            # one more char, to get to the next field.
            cursor_str += ' '
        text = self._cmd.prefix() + ' '.join(parts)
        if immediate and self._cursor_part == len(parts) - 1:
            # If we should complete immediately and we're completing the last
            # part in the commandline, we automatically add a space.
            text += ' '
        self._cmd.setText(text)
        log.completion.debug("Placing cursor after '{}'".format(cursor_str))
        log.modes.debug("Completion triggered, focusing {!r}".format(self))
        self._cmd.setCursorPosition(len(cursor_str))
        self._cmd.setFocus()
        self._cmd.show_cmd.emit()

    @pyqtSlot()
    def on_text_edited(self):
        """Reset _empty_item_idx if text was edited."""
        self._empty_item_idx = None
        # We also want to update the cursor part and emit update_completion
        # here, but that's already done for us by cursorPositionChanged
        # anyways, so we don't need to do it twice.
