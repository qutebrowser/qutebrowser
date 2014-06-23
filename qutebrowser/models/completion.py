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

"""CompletionModels for different usages."""

from PyQt5.QtCore import pyqtSlot, Qt, QCoreApplication

import qutebrowser.config.config as config
import qutebrowser.config.configdata as configdata
from qutebrowser.models.basecompletion import BaseCompletionModel
from qutebrowser.commands.utils import cmd_dict
from qutebrowser.utils.log import completion as logger
from qutebrowser.utils.qt import qt_ensure_valid


class SettingSectionCompletionModel(BaseCompletionModel):

    """A CompletionModel filled with settings sections."""

    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        cat = self.new_category("Sections")
        for name in configdata.DATA.keys():
            desc = configdata.SECTION_DESC[name].splitlines()[0].strip()
            self.new_item(cat, name, desc)


class SettingOptionCompletionModel(BaseCompletionModel):

    """A CompletionModel filled with settings and their descriptions.

    Attributes:
        _section: The section of this model.
        _misc_items: A dict of the misc. column items which will be set later.
    """

    # pylint: disable=abstract-method

    def __init__(self, section, parent=None):
        super().__init__(parent)
        cat = self.new_category(section)
        sectdata = configdata.DATA[section]
        self._misc_items = {}
        self._section = section
        for name, _ in sectdata.items():
            try:
                desc = sectdata.descriptions[name]
            except (KeyError, AttributeError):
                # Some stuff (especially ValueList items) don't have a
                # description.
                desc = ""
            value = config.get(section, name, raw=True)
            _valitem, _descitem, miscitem = self.new_item(cat, name, desc,
                                                          value)
            self._misc_items[name] = miscitem

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update misc column when config changed."""
        if section != self._section:
            return
        try:
            item = self._misc_items[option]
        except KeyError:
            logger.debug("Couldn't get item {}.{} from model!".format(
                section, option))
            # changed before init
            return
        val = config.get(section, option, raw=True)
        idx = item.index()
        qt_ensure_valid(idx)
        ok = self.setData(idx, val, Qt.DisplayRole)
        if not ok:
            raise ValueError("Setting data failed! (section: {}, option: {}, "
                             "value: {})".format(section, option, val))


class SettingValueCompletionModel(BaseCompletionModel):

    """A CompletionModel filled with setting values."""

    # pylint: disable=abstract-method

    def __init__(self, section, option=None, parent=None):
        super().__init__(parent)
        cur_cat = self.new_category("Current", sort=0)
        value = config.get(section, option, raw=True)
        if not value:
            value = '""'
        self.cur_item, _descitem, _miscitem = self.new_item(cur_cat, value,
                                                            "Current value")
        if hasattr(configdata.DATA[section], 'valtype'):
            # Same type for all values (ValueList)
            vals = configdata.DATA[section].valtype.complete()
        else:
            if option is None:
                raise ValueError("option may only be None for ValueList "
                                 "sections, but {} is not!".format(section))
            # Different type for each value (KeyValue)
            vals = configdata.DATA[section][option].typ.complete()
        if vals is not None:
            cat = self.new_category("Allowed", sort=1)
            for (val, desc) in vals:
                self.new_item(cat, val, desc)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update current value when config changed."""
        value = config.get(section, option, raw=True)
        if not value:
            value = '""'
        idx = self.cur_item.index()
        qt_ensure_valid(idx)
        ok = self.setData(idx, value, Qt.DisplayRole)
        if not ok:
            raise ValueError("Setting data failed! (section: {}, option: {}, "
                             "value: {})".format(section, option, value))


class CommandCompletionModel(BaseCompletionModel):

    """A CompletionModel filled with all commands and descriptions."""

    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        assert cmd_dict
        cmdlist = []
        for obj in set(cmd_dict.values()):
            if obj.hide or (obj.debug and not
                            QCoreApplication.instance().args.debug):
                pass
            else:
                cmdlist.append((obj.name, obj.desc))
        for name, cmd in config.section('aliases').items():
            cmdlist.append((name, "Alias for '{}'".format(cmd)))
        cat = self.new_category("Commands")
        for (name, desc) in sorted(cmdlist):
            self.new_item(cat, name, desc)
