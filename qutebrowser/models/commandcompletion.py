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

"""A CompletionModel filled with all commands and descriptions."""

from collections import OrderedDict

from qutebrowser.commands.utils import cmd_dict
from qutebrowser.models.completion import CompletionModel


class CommandCompletionModel(CompletionModel):

    """A CompletionModel filled with all commands and descriptions."""

    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        assert cmd_dict
        cmdlist = []
        for obj in set(cmd_dict.values()):
            if not obj.hide:
                cmdlist.append([obj.name, obj.desc])
        data = OrderedDict()
        data['Commands'] = sorted(cmdlist)
        self.init_data(data)
