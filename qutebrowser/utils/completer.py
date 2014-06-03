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

import qutebrowser.config.config as config
import qutebrowser.config.configdata as configdata
import qutebrowser.commands.utils as cmdutils
from qutebrowser.utils.log import completion as logger
from qutebrowser.models.completionfilter import CompletionFilterModel as CFM
from qutebrowser.models.completion import (
    CommandCompletionModel, SettingSectionCompletionModel,
    SettingOptionCompletionModel, SettingValueCompletionModel)
from qutebrowser.models.basecompletion import NoCompletionsError
from qutebrowser.utils.usertypes import FakeDict
from qutebrowser.utils.log import completion as logger


class Completer(QObject):

    """Completer which manages completions in a CompletionView.

    Attributes:
        view: The CompletionView associated with this completer.
        ignore_change: Whether to ignore the next completion update.
        _models: dict of available completion models.
        _lastmodel: The model set in the last iteration.

    Signals:
        change_completed_part: Text which should be substituted for the word
                               we're currently completing.
                               arg 0: The text to change to.
                               arg 1: True if the text should be set
                                      immediately, without continuing
                                      completing the current field.
    """

    change_completed_part = pyqtSignal(str, bool)

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.ignore_change = False
        self._lastmodel = None

        self._models = {
            'option': {},
            'value': {},
        }
        self._init_command_completion()
        self._init_setting_completions()

    def _init_command_completion(self):
        """Initialize the command completion model."""
        self._models['command'] = CFM(CommandCompletionModel(self))

    def _init_setting_completions(self):
        """Initialize setting completion models."""
        self._models['section'] = CFM(SettingSectionCompletionModel(self))
        self._models['option'] = {}
        self._models['value'] = {}
        for sectname, sect in configdata.DATA.items():
            optmodel = CFM(SettingOptionCompletionModel(sectname, self))
            self._models['option'][sectname] = optmodel
            config.instance().changed.connect(
                optmodel.srcmodel.on_config_changed)
            if hasattr(sect, 'valtype'):
                # Same type for all values (ValueList)
                try:
                    model = CFM(SettingValueCompletionModel(
                        sectname, parent=self))
                    self._models['value'][sectname] = FakeDict(model)
                except NoCompletionsError:
                    pass
            else:
                self._models['value'][sectname] = {}
                for opt in configdata.DATA[sectname].keys():
                    try:
                        self._models['value'][sectname][opt] = CFM(
                            SettingValueCompletionModel(sectname, opt, self))
                    except NoCompletionsError:
                        pass

    def _get_new_completion(self, parts, cursor_part):
        """Get a new completion model.

        Args:
            parts: The command chunks to get a completion for.
            cursor_part: The part the cursor is over currently.
        """
        logger.debug("cursor part: {}".format(cursor_part))
        if cursor_part == 0:
            # '|' or 'set|'
            return self._models['command']
        # delegate completion to command
        try:
            completions = cmdutils.cmd_dict[parts[0]].completion
        except KeyError:
            # entering an unknown command
            return None
        logger.debug("completions: {}".format(completions))
        if completions is None:
            # command without any available completions
            return None
        try:
            idx = cursor_part - 1
            completion_name = completions[idx]
            logger.debug('modelname {}'.format(completion_name))
        except IndexError:
            # More arguments than completions
            return None
        if completion_name == 'option':
            section = parts[cursor_part - 1]
            model = self._models['option'].get(section)
        elif completion_name == 'value':
            section = parts[cursor_part - 2]
            option = parts[cursor_part - 1]
            try:
                model = self._models['value'][section][option]
            except KeyError:
                model = None
        else:
            model = self._models.get(completion_name)
        return model

    def selection_changed(self, selected, deselected):
        """Emit change_completed_part if a new item was selected.

        Called from the views selectionChanged method.

        Args:
            selected: New selection.
            delected: Previous selection.

        Emit:
            change_completed_part: Emitted when there's data for the new item.
        """
        indexes = selected.indexes()
        if not indexes:
            return
        model = self.view.model()
        data = model.data(indexes[0])
        if data is None:
            return
        if model.item_count == 1 and config.get('completion',
                                                'quick-complete'):
            # If we only have one item, we want to apply it immediately
            # and go on to the next part.
            self.change_completed_part.emit(data, True)
        else:
            self.ignore_change = True
            self.change_completed_part.emit(data, False)
            self.ignore_change = False

    @pyqtSlot(str, list, int)
    def on_update_completion(self, prefix, parts, cursor_part):
        """Check if completions are available and activate them.

        Slot for the textChanged signal of the statusbar command widget.

        Args:
            text: The new text
            cursor_part: The part the cursor is currently over.
        """
        if self.ignore_change:
            logger.debug("Ignoring completion update")
            return

        logger.debug("Updating completion, parts: {}, cursor_part {}".format(
            parts, cursor_part))

        if prefix != ':':
            # This is a search or gibberish, so we don't need to complete
            # anything (yet)
            # FIXME complete searchs
            self.view.hide()
            return

        model = self._get_new_completion(parts, cursor_part)
        if model is None:
            logger.debug("No completion model for {}.".format(parts))
        else:
            logger.debug("New completion: {} / last: {}".format(
                model.srcmodel.__class__.__name__,
                self._lastmodel.srcmodel.__class__.__name__ if self._lastmodel
                is not None else "None"))
        if model != self._lastmodel:
            self._lastmodel = model
            if model is None:
                self.view.hide()
                return
            self.view.set_model(model)

        if model is None:
            return

        pattern = parts[cursor_part] if parts else ''
        logger.debug("pattern: {}".format(pattern))
        self.view.model().pattern = pattern

        if self.view.model().item_count == 0:
            self.view.hide()
            return

        self.view.model().mark_all_items(pattern)
        if self.view._enabled:
            self.view.show()

