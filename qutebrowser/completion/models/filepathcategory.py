# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Completion category for filesystem paths."""

import glob
import os

from PyQt5.QtCore import (QAbstractListModel, QModelIndex)

class FilePathCategory(QAbstractListModel):
    """Represent filesystem paths matching a pattern."""

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paths: list = []
        self.name = name
        self.columns_to_filter = [0]

    def set_pattern(self, val):
        """Setter for pattern.

        Args:
            val: The value to set.
        """
        glob_str = os.path.expanduser(glob.escape(val)) + '*'
        self._paths = sorted(glob.glob(glob_str))

    def data(self, index: QModelIndex):
        """Implement abstract method in QAbstractListModel.
        """
        if index.column() == 0:
            return self._paths[index.row()]
        else:
            return ''

    def rowCount(self, *_args):
        """Implement abstract method in QAbstractListModel.
        """
        return len(self._paths)

