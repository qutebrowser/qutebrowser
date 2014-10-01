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

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject

from qutebrowser.config import config, configdata
from qutebrowser.commands import cmdutils
from qutebrowser.utils import usertypes, log, objreg, utils
from qutebrowser.models import completion as models
from qutebrowser.models.completionfilter import CompletionFilterModel as CFM


class Completer(QObject):

    """Completer which manages completions in a CompletionView.

    Attributes:
        _ignore_change: Whether to ignore the next completion update.
        _models: dict of available completion models.

    Signals:
        change_completed_part: Text which should be substituted for the word
                               we're currently completing.
                               arg 0: The text to change to.
                               arg 1: True if the text should be set
                                      immediately, without continuing
                                      completing the current field.
    """

    change_completed_part = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ignore_change = False

        self._models = {
            usertypes.Completion.option: {},
            usertypes.Completion.value: {},
        }
        self._init_static_completions()
        self._init_setting_completions()

    def __repr__(self):
        return utils.get_repr(self)

    def _model(self):
        """Convienience method to get the current completion model."""
        return objreg.get('completion').model()

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

    def _get_new_completion(self, parts, cursor_part):
        """Get a new completion model.

        Args:
            parts: The command chunks to get a completion for.
            cursor_part: The part the cursor is over currently.
        """
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

        Emit:
            change_completed_part: Emitted when there's data for the new item.
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
            self._ignore_change = False

    @pyqtSlot(str, list, int)
    def on_update_completion(self, prefix, parts, cursor_part):
        """Check if completions are available and activate them.

        Slot for the textChanged signal of the statusbar command widget.

        Args:
            text: The new text
            cursor_part: The part the cursor is currently over.
        """
        if self._ignore_change:
            log.completion.debug("Ignoring completion update")
            return

        completion = objreg.get('completion')

        if prefix != ':':
            # This is a search or gibberish, so we don't need to complete
            # anything (yet)
            # FIXME complete searchs
            # https://github.com/The-Compiler/qutebrowser/issues/32
            completion.hide()
            return

        model = self._get_new_completion(parts, cursor_part)

        if model != self._model():
            if model is None:
                completion.hide()
            else:
                completion.set_model(model)

        if model is None:
            log.completion.debug("No completion model for {}.".format(parts))
            return

        pattern = parts[cursor_part] if parts else ''
        self._model().set_pattern(pattern)

        log.completion.debug(
            "New completion for {}: {}, with pattern '{}'".format(
                parts, model.sourceModel().__class__.__name__, pattern))

        if self._model().count() == 0:
            completion.hide()
            return

        self._model().mark_all_items(pattern)
        if completion.enabled:
            completion.show()
