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
from typing import Any
import urllib.parse

from PyQt5.QtCore import (QAbstractListModel, QModelIndex)


class FilePathCategory(QAbstractListModel):
    """Represent filesystem paths matching a pattern."""

    def __init__(self, name: str):
        super().__init__()
        self._paths: list = []
        self.name = name
        self.columns_to_filter = [0]

    def set_pattern(self, val: str) -> None:
        """Compute list of suggested paths. (Called from `CompletionModel`.)

        Args:
            val: The user's partially typed URL/path.
        """
        if not val:
            self._paths = [os.path.expanduser('~')]
        elif len(val) >= 1 and val[0] in ['~', '/']:
            glob_str = os.path.expanduser(glob.escape(val)) + '*'
            self._paths = sorted(glob.glob(glob_str))
        elif len(val) >= 8 and val[:8] == 'file:///':
            glob_str = os.path.expanduser(urllib.parse.unquote(val[7:])) + '*'
            self._paths = sorted(glob.glob(glob_str))
        else:
            self._paths = []

    def data(self, index: QModelIndex) -> str:
        """Implement abstract method in QAbstractListModel."""
        if index.column() == 0:
            return self._paths[index.row()]
        else:
            return ''

    def rowCount(self, *_args: Any) -> int:
        """Implement abstract method in QAbstractListModel."""
        return len(self._paths)
