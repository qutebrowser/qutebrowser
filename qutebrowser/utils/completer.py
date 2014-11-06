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

"""Completer attached to a CompletionView."""

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject, QTimer

from qutebrowser.config import config, configdata
from qutebrowser.commands import cmdutils
from qutebrowser.utils import usertypes, log, objreg, utils
from qutebrowser.models import completion as models
from qutebrowser.models.completionfilter import CompletionFilterModel as CFM


class Completer(QObject):

    """Completer which manages completions in a CompletionView.

    Attributes:
        _ignore_change: Whether to ignore the next completion update.
        models: dict of available completion models.
        _win_id: The window ID this completer is in.
        _timer: The timer used to trigger the completion update.
        _prefix: The prefix to be used for the next completion update.
        _parts: The parts to be used for the next completion update.
        _cursor_part: The cursor part index for the next completion update.

    Signals:
        change_completed_part: Text which should be substituted for the word
                               we're currently completing.
                               arg 0: The text to change to.
                               arg 1: True if the text should be set
                                      immediately, without continuing
                                      completing the current field.
    """

    change_completed_part = pyqtSignal(str, bool)

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self._ignore_change = False

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
        self._prefix = None
        self._parts = None
        self._cursor_part = None

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
        parts, cursor_part = self._filter_cmdline_parts(parts, cursor_part)
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
        """Emit change_completed_part if a new item was selected.

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
            self.change_completed_part.emit(data, True)
        else:
            self._ignore_change = True
            self.change_completed_part.emit(data, False)

    @pyqtSlot(str, list, int)
    def on_update_completion(self, prefix, parts, cursor_part):
        """Schedule updating/enabling completion.

        Slot for the textChanged signal of the statusbar command widget.

        For performance reasons we don't want to block here, instead we do this
        in the background.
        """
        self._timer.start()
        log.completion.debug("Scheduling completion update. prefix {}, parts "
                             "{}, cursor_part {}".format(prefix, parts,
                                                         cursor_part))
        self._prefix = prefix
        self._parts = parts
        self._cursor_part = cursor_part

    @pyqtSlot()
    def update_completion(self):
        """Check if completions are available and activate them."""

        assert self._prefix is not None
        assert self._parts is not None
        assert self._cursor_part is not None

        log.completion.debug("Updating completion - prefix {}, parts {}, "
                             "cursor_part {}".format(self._prefix, self._parts,
                                                     self._cursor_part))
        if self._ignore_change:
            self._ignore_change = False
            log.completion.debug("Ignoring completion update")
            return

        completion = objreg.get('completion', scope='window',
                                window=self._win_id)

        if self._prefix != ':':
            # This is a search or gibberish, so we don't need to complete
            # anything (yet)
            # FIXME complete searchs
            # https://github.com/The-Compiler/qutebrowser/issues/32
            completion.hide()
            return

        model = self._get_new_completion(self._parts, self._cursor_part)

        if model != self._model():
            if model is None:
                completion.hide()
            else:
                completion.set_model(model)

        if model is None:
            log.completion.debug("No completion model for {}.".format(
                self._parts))
            return

        try:
            pattern = self._parts[self._cursor_part] if self._parts else ''
        except IndexError:
            pattern = ''
        self._model().set_pattern(pattern)

        log.completion.debug(
            "New completion for {}: {}, with pattern '{}'".format(
                self._parts, model.srcmodel.__class__.__name__, pattern))

        if self._model().count() == 0:
            completion.hide()
            return

        if completion.enabled:
            completion.show()
