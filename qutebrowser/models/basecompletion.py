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

"""The base completion model for completion in the command line.

Module attributes:
    Role: An enum of user defined model roles.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem

from qutebrowser.utils.usertypes import enum


Role = enum('marks', 'sort', start=Qt.UserRole)


class NoCompletionsError(Exception):

    """Gets raised when there are no completions available."""

    pass


class BaseCompletionModel(QStandardItemModel):

    """A simple QStandardItemModel adopted for completions.

    Used for showing completions later in the CompletionView. Supports setting
    marks and adding new categories/items easily.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)

    def _get_marks(self, needle, haystack):
        """Return the marks for needle in haystack.

        Args:
            needle: The substring which should match.
            haystack: The string where the matches should be in.

        Return:
            A list of (startidx, endidx) tuples.
        """
        pos1 = pos2 = 0
        marks = []
        if not needle:
            return marks
        while True:
            pos1 = haystack.find(needle, pos2)
            if pos1 == -1:
                break
            pos2 = pos1 + len(needle)
            marks.append((pos1, pos2))
        return marks

    def mark_item(self, index, needle):
        """Mark a string in the givem item.

        Args:
            index: A QModelIndex of the item to mark.
            needle: The string to mark.
        """
        haystack = self.data(index)
        marks = self._get_marks(needle, haystack)
        self.setData(index, marks, Role.marks)

    def new_category(self, name):
        """Add a new category to the model.

        Args:
            name: The name of the category to add.

        Return:
            The created QStandardItem.
        """
        cat = QStandardItem(name)
        self.appendRow(cat)
        return cat

    def new_item(self, cat, name, desc='', misc=None):
        """Add a new item to a category.

        Args:
            cat: The parent category.
            name: The name of the item.
            desc: The description of the item.
            misc: Misc text to display.

        Return:
            A (nameitem, descitem, miscitem) tuple.
        """
        nameitem = QStandardItem(name)
        descitem = QStandardItem(desc)
        if misc is None:
            miscitem = QStandardItem()
        else:
            miscitem = QStandardItem(misc)
        idx = cat.rowCount()
        cat.setChild(idx, 0, nameitem)
        cat.setChild(idx, 1, descitem)
        cat.setChild(idx, 2, miscitem)
        return nameitem, descitem, miscitem

    def flags(self, index):
        """Return the item flags for index.

        Override QAbstractItemModel::flags.

        Args:
            index: The QModelIndex to get item flags for.

        Return:
            The item flags, or Qt.NoItemFlags on error.
        """
        if not index.isValid():
            return Qt.NoItemFlags
        if index.parent().isValid():
            # item
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        else:
            # category
            return Qt.NoItemFlags

    def sort(self, column, order=Qt.AscendingOrder):
        """Sort the data in column according to order.

        Override QAbstractItemModel::sort.

        Raise:
            NotImplementedError, should be overwritten in a superclass.
        """
        raise NotImplementedError
