# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""CompletionModels for the config."""

from PyQt5.QtCore import pyqtSlot, Qt

from qutebrowser.config import config, configdata
from qutebrowser.utils import log, qtutils, objreg
from qutebrowser.completion.models import base


class SettingSectionCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with settings sections."""

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    COLUMN_WIDTHS = (20, 70, 10)

    def __init__(self, parent=None):
        super().__init__(parent)
        cat = self.new_category("Sections")
        for name in configdata.DATA:
            desc = configdata.SECTION_DESC[name].splitlines()[0].strip()
            self.new_item(cat, name, desc)


class SettingOptionCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with settings and their descriptions.

    Attributes:
        _misc_items: A dict of the misc. column items which will be set later.
        _section: The config section this model shows.
    """

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    COLUMN_WIDTHS = (20, 70, 10)

    def __init__(self, section, parent=None):
        super().__init__(parent)
        cat = self.new_category(section)
        sectdata = configdata.DATA[section]
        self._misc_items = {}
        self._section = section
        objreg.get('config').changed.connect(self.update_misc_column)
        for name in sectdata:
            try:
                desc = sectdata.descriptions[name]
            except (KeyError, AttributeError):
                # Some stuff (especially ValueList items) don't have a
                # description.
                desc = ""
            else:
                desc = desc.splitlines()[0]
            value = config.get(section, name, raw=True)
            _valitem, _descitem, miscitem = self.new_item(cat, name, desc,
                                                          value)
            self._misc_items[name] = miscitem

    @pyqtSlot(str, str)
    def update_misc_column(self, section, option):
        """Update misc column when config changed."""
        if section != self._section:
            return
        try:
            item = self._misc_items[option]
        except KeyError:
            log.completion.debug("Couldn't get item {}.{} from model!".format(
                section, option))
            # changed before init
            return
        val = config.get(section, option, raw=True)
        idx = item.index()
        qtutils.ensure_valid(idx)
        ok = self.setData(idx, val, Qt.DisplayRole)
        if not ok:
            raise ValueError("Setting data failed! (section: {}, option: {}, "
                             "value: {})".format(section, option, val))


class SettingValueCompletionModel(base.BaseCompletionModel):

    """A CompletionModel filled with setting values.

    Attributes:
        _section: The config section this model shows.
        _option: The config option this model shows.
    """

    # https://github.com/The-Compiler/qutebrowser/issues/545
    # pylint: disable=abstract-method

    COLUMN_WIDTHS = (20, 70, 10)

    def __init__(self, section, option, parent=None):
        super().__init__(parent)
        self._section = section
        self._option = option
        objreg.get('config').changed.connect(self.update_current_value)
        cur_cat = self.new_category("Current/Default", sort=0)
        value = config.get(section, option, raw=True)
        if not value:
            value = '""'
        self.cur_item, _descitem, _miscitem = self.new_item(cur_cat, value,
                                                            "Current value")
        default_value = configdata.DATA[section][option].default()
        if not default_value:
            default_value = '""'
        self.new_item(cur_cat, default_value, "Default value")
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
            cat = self.new_category("Completions", sort=1)
            for (val, desc) in vals:
                self.new_item(cat, val, desc)

    @pyqtSlot(str, str)
    def update_current_value(self, section, option):
        """Update current value when config changed."""
        if (section, option) != (self._section, self._option):
            return
        value = config.get(section, option, raw=True)
        if not value:
            value = '""'
        idx = self.cur_item.index()
        qtutils.ensure_valid(idx)
        ok = self.setData(idx, value, Qt.DisplayRole)
        if not ok:
            raise ValueError("Setting data failed! (section: {}, option: {}, "
                             "value: {})".format(section, option, value))
