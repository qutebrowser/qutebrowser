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

"""The base completion model for completion in the command line."""

from PyQt5.QtCore import Qt, QVariant, QAbstractItemModel, QModelIndex


class CompletionModel(QAbstractItemModel):

    """A simple tree model based on Python OrderdDict containing tuples.

    Used for showing completions later in the CompletionView.

    Attributes:
        _id_map: A mapping from Python object IDs (from id()) to objects, to be
                 used as internalIndex for the model.
        _root: The root item.

    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._id_map = {}
        self._root = CompletionItem([""] * 2)
        self._id_map[id(self._root)] = self._root

    def _node(self, index):
        """Return the interal data representation for index.

        Args:
            index: The QModelIndex to get data for.

        Return:
            The CompletionItem for index, or the root CompletionItem if the
            index was invalid.

        """
        if index.isValid():
            return self._id_map[index.internalId()]
        else:
            return self._root

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

    def mark_all_items(self, needle):
        """Mark a string in all items (children of root-children).

        Args:
            needle: The string to mark.

        """
        for i in range(self.rowCount()):
            cat = self.index(i, 0)
            for k in range(self.rowCount(cat)):
                idx = self.index(k, 0, cat)
                old = self.data(idx).value()
                marks = self._get_marks(needle, old)
                self.setData(idx, marks, Qt.UserRole)

    def init_data(self, data):
        """Initialize the Qt model based on the data given.

        Args:
            data: dict of data to process.

        """
        for (cat, items) in data.items():
            newcat = CompletionItem([cat], self._root)
            self._id_map[id(newcat)] = newcat
            self._root.children.append(newcat)
            for item in items:
                newitem = CompletionItem(item, newcat)
                self._id_map[id(newitem)] = newitem
                newcat.children.append(newitem)

    def removeRows(self, position=0, count=1, parent=QModelIndex()):
        """Remove rows from the model.

        Override QAbstractItemModel::removeRows.

        Args:
            position: The start row to remove.
            count: How many rows to remove.
            parent: The parent QModelIndex.

        """
        node = self._node(parent)
        self.beginRemoveRows(parent, position, position + count - 1)
        node.children.pop(position)
        self.endRemoveRows()

    def columnCount(self, parent=QModelIndex()):
        """Return the column count in the model.

        Override QAbstractItemModel::columnCount.

        Args:
            parent: The parent for which to return the column count. Currently
                    ignored.

        Return:
            Column count as an integer.

        """
        # pylint: disable=unused-argument
        return self._root.column_count()

    def rowCount(self, parent=QModelIndex()):
        """Return the children count of an item.

        Use the root frame if parent is invalid.
        Override QAbstractItemModel::rowCount.

        Args:
            parent: The parent for which to return the row count.

        Return:
            Row count as an integer.

        """
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            pitem = self._root
        else:
            pitem = self._id_map[parent.internalId()]

        return len(pitem.children)

    def data(self, index, role=Qt.DisplayRole):
        """Return the data for role/index as QVariant.

        Override QAbstractItemModel::data.

        Args:
            index: The QModelIndex for which to get data for.
            roel: The role to use for the data.

        Return:
            The data as QVariant or an invalid QVariant on error.

        """
        if not index.isValid():
            return QVariant()
        try:
            item = self._id_map[index.internalId()]
        except KeyError:
            return QVariant()
        try:
            return QVariant(item.data(index.column(), role))
        except (IndexError, ValueError):
            return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return the header data for role/index as QVariant.

        Override QAbstractItemModel::headerData.

        Args:
            section: The section (as int) for which to get the header data.
            orientation: Qt.Vertical or Qt.Horizontal

        Return:
            The data as QVariant or an invalid QVariant on error.

        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self._root.data(section))
        return QVariant()

    def setData(self, index, value, role=Qt.EditRole):
        """Set the data for role/index to value.

        Override QAbstractItemModel::setData.

        Args:
            index: The QModelIndex where to set the data.
            value: The new data value.
            role: The role to set the data for.

        Return:
            True on success, False on failure.

        Emit:
            dataChanged when the data was changed.

        """
        if not index.isValid():
            return False
        item = self._id_map[index.internalId()]
        try:
            item.setdata(index.column(), value, role)
        except (IndexError, ValueError):
            return False
        self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        """Return the item flags for index.

        Override QAbstractItemModel::flags.

        Args:
            index: The QModelIndex to get item flags for.

        Return:
            The item flags, or Qt.NoItemFlags on error.

        """
        # FIXME categories are not selectable, but moving via arrow keys still
        # tries to select them
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsEnabled
        if len(self._id_map[index.internalId()].children) > 0:
            return flags
        else:
            return flags | Qt.ItemIsSelectable

    def index(self, row, column, parent=QModelIndex()):
        """Return the QModelIndex for row/column/parent.

        Override QAbstractItemModel::index.

        Args:
            row: The row (int) to get an index for.
            column: The column (int) to get an index for.
            parent: The parent (QModelIndex) to get an index for.

        Return:
            A generated QModelIndex or an invalid QModelIndex on failure.

        """
        if (0 <= row < self.rowCount(parent) and
                0 <= column < self.columnCount(parent)):
            pass
        else:
            return QModelIndex()

        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item = self._id_map[parent.internalId()]

        child_item = parent_item.children[row]
        if child_item:
            index = self.createIndex(row, column, id(child_item))
            self._id_map.setdefault(index.internalId(), child_item)
            return index
        else:
            return QModelIndex()

    def parent(self, index):
        """Return the QModelIndex of the parent of the object behind index.

        Override QAbstractItemModel::parent.

        Args:
            index: The QModelIndex to get the parent for.

        Return:
            The parent's QModelIndex or an invalid QModelIndex on failure.

        """
        if not index.isValid():
            return QModelIndex()
        item = self._id_map[index.internalId()].parent
        if item == self._root or item is None:
            return QModelIndex()
        return self.createIndex(item.row(), 0, id(item))

    def sort(self, column, order=Qt.AscendingOrder):
        """Sort the data in column according to order.

        Override QAbstractItemModel::sort.

        Raise:
            NotImplementedError, should be overwritten in a superclass.

        """
        raise NotImplementedError


class CompletionItem():

    """An item (row) in a CompletionModel.

    Attributes:
        parent: The parent of this item.
        children: The children of this item.
        _data: The data of this item.
        _marks: The marks of this item.

    """

    def __init__(self, data, parent=None):
        """Constructor for CompletionItem.

        Args:
            data: The data for the model, as tuple (columns).
            parent: An optional parent item.

        """
        self.parent = parent
        self.children = []
        self._data = data
        self._marks = []

    def data(self, column, role=Qt.DisplayRole):
        """Get the data for role/column.

        Args:
            column: The column (int) to get data for.
            role: The role to get data for.

        Return:
            The requested data.

        Raise:
            ValueError if the role is invalid.

        """
        if role == Qt.DisplayRole:
            return self._data[column]
        elif role == Qt.UserRole:
            return self._marks
        else:
            raise ValueError("Invalid role {}".format(role))

    def setdata(self, column, value, role=Qt.DisplayRole):
        """Set the data for column/role to value.

        Args:
            column: The column (int) to set the data for.
            value: The value to set the data to.
            role: The role to set the data for.

        Raise:
            ValueError if the role is invalid.

        """
        if role == Qt.DisplayRole:
            self._data[column] = value
        elif role == Qt.UserRole:
            self._marks = value
        else:
            raise ValueError("Invalid role {}".format(role))

    def column_count(self):
        """Get the column count in the item.

        Return:
            The column count.

        """
        return len(self._data)

    def row(self):
        """Get the row index (int) of the item.

        Return:
            The row index of the item, or 0 if we're a root item.

        """
        if self.parent:
            return self.parent.children.index(self)
        return 0
