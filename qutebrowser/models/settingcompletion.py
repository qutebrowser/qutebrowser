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

"""A CompletionModel filled with settings and their descriptions."""

import logging

from collections import OrderedDict

from qutebrowser.models.completion import CompletionModel
from qutebrowser.config.configdata import configdata


class SettingCompletionModel(CompletionModel):

    """A CompletionModel filled with settings and their descriptions."""

    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)
        data = OrderedDict()
        for secname, secdata in configdata().items():
            newdata = []
            for name in secdata.values.keys():
                newdata.append((name, secdata.descriptions[name]))
            data[secname] = newdata
        logging.debug("Setting data: {}".format(data))
        self.init_data(data)
