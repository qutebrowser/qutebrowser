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

"""CompletionModels for settings/sections."""

from qutebrowser.models.completion import CompletionModel
from qutebrowser.config.configdata import configdata


class SettingSectionCompletionModel(CompletionModel):

    """A CompletionModel filled with settings sections."""

    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        cat = self.new_category("Config sections")
        for name in configdata().keys():
            self.new_item(cat, name)


class SettingOptionCompletionModel(CompletionModel):

    """A CompletionModel filled with settings and their descriptions."""

    # pylint: disable=abstract-method

    def __init__(self, section, parent=None):
        super().__init__(parent)
        cat = self.new_category("Config options for {}".format(section))
        sectdata = configdata()[section]
        for name, _ in sectdata.items():
            try:
                desc = sectdata.descriptions[name]
            except (KeyError, AttributeError):
                desc = ""
            self.new_item(cat, name, desc)
