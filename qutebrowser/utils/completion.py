"""The base data models for completion in the commandline.

Contains:
    CompletionModel       -- A simple tree model based on Python data.
    CompletionItem        -- One item in the CompletionModel.
    CompletionFilterModel -- A QSortFilterProxyModel subclass for completions.

"""

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

from collections import OrderedDict

from PyQt5.QtCore import (QAbstractItemModel, Qt, QModelIndex, QVariant,
                          QSortFilterProxyModel)


class CompletionModel(QAbstractItemModel):

    """A simple tree model based on Python OrderdDict containing tuples.

    Used for showing completions later in the CompletionView.

    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = OrderedDict()
        self.parents = []
        self.id_map = {}
        self.root = CompletionItem([""] * 2)
        self.id_map[id(self.root)] = self.root

    def removeRows(self, position=0, count=1, parent=QModelIndex()):
        """Remove rows from the model.

        Override QAbstractItemModel::removeRows.

        """
        node = self._node(parent)
        self.beginRemoveRows(parent, position, position + count - 1)
        node.children.pop(position)
        self.endRemoveRows()

    def _node(self, index):
        """Return the interal data representation for index.

        Return the CompletionItem for index, or the root CompletionItem if the
        index was invalid.

        """
        if index.isValid():
            return self.id_map[index.internalId()]
        else:
            return self.root

    def columnCount(self, parent=QModelIndex()):
        """Return the column count in the model.

        Override QAbstractItemModel::columnCount.

        """
        # pylint: disable=unused-argument
        return self.root.column_count()

    def data(self, index, role=Qt.DisplayRole):
        """Return the data for role/index as QVariant.

        Return an invalid QVariant on error.
        Override QAbstractItemModel::data.

        """
        if not index.isValid():
            return QVariant()
        try:
            item = self.id_map[index.internalId()]
        except KeyError:
            return QVariant()
        try:
            return QVariant(item.data(index.column(), role))
        except (IndexError, ValueError):
            return QVariant()

    def flags(self, index):
        """Return the item flags for index.

        Return Qt.NoItemFlags on error.
        Override QAbstractItemModel::flags.

        """
        # FIXME categories are not selectable, but moving via arrow keys still
        # tries to select them
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsEnabled
        if len(self.id_map[index.internalId()].children) > 0:
            return flags
        else:
            return flags | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return the header data for role/index as QVariant.

        Return an invalid QVariant on error.
        Override QAbstractItemModel::headerData.

        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.root.data(section))
        return QVariant()

    def setData(self, index, value, role=Qt.EditRole):
        """Set the data for role/index to value.

        Return True on success, False on failure.
        Override QAbstractItemModel::setData.

        """
        if not index.isValid():
            return False
        item = self.id_map[index.internalId()]
        try:
            item.setdata(index.column(), value, role)
        except (IndexError, ValueError):
            return False
        self.dataChanged.emit(index, index)
        return True

    def index(self, row, column, parent=QModelIndex()):
        """Return the QModelIndex for row/column/parent.

        Return an invalid QModelIndex on failure.
        Override QAbstractItemModel::index.

        """
        if (0 <= row < self.rowCount(parent) and
                0 <= column < self.columnCount(parent)):
            pass
        else:
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root
        else:
            parent_item = self.id_map[parent.internalId()]

        child_item = parent_item.children[row]
        if child_item:
            index = self.createIndex(row, column, id(child_item))
            self.id_map.setdefault(index.internalId(), child_item)
            return index
        else:
            return QModelIndex()

    def parent(self, index):
        """Return the QModelIndex of the parent of the object behind index.

        Return an invalid QModelIndex on failure.
        Override QAbstractItemModel::parent.

        """
        if not index.isValid():
            return QModelIndex()
        item = self.id_map[index.internalId()].parent
        if item == self.root or item is None:
            return QModelIndex()
        return self.createIndex(item.row(), 0, id(item))

    def rowCount(self, parent=QModelIndex()):
        """Return the children count of an item.

        Use the root frame if parent is invalid.
        Override QAbstractItemModel::rowCount.

        """
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            pitem = self.root
        else:
            pitem = self.id_map[parent.internalId()]

        return len(pitem.children)

    def sort(self, column, order=Qt.AscendingOrder):
        """Sort the data in column according to order.

        Raise NotImplementedError, should be overwritten in a superclass.
        Override QAbstractItemModel::sort.

        """
        raise NotImplementedError

    def init_data(self):
        """Initialize the Qt model based on the data in self._data."""
        for (cat, items) in self._data.items():
            newcat = CompletionItem([cat], self.root)
            self.id_map[id(newcat)] = newcat
            self.root.children.append(newcat)
            for item in items:
                newitem = CompletionItem(item, newcat)
                self.id_map[id(newitem)] = newitem
                newcat.children.append(newitem)

    def mark_all_items(self, needle):
        """Mark a string in all items (children of root-children).

        needle -- The string to mark.

        """
        for i in range(self.rowCount()):
            cat = self.index(i, 0)
            for k in range(self.rowCount(cat)):
                idx = self.index(k, 0, cat)
                old = self.data(idx).value()
                marks = self._get_marks(needle, old)
                self.setData(idx, marks, Qt.UserRole)

    def _get_marks(self, needle, haystack):
        """Return the marks for needle in haystack."""
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


class CompletionItem():

    """An item (row) in a CompletionModel."""

    parent = None
    children = None
    _data = None
    _marks = None

    def __init__(self, data, parent=None):
        """Constructor for CompletionItem.

        data   -- The data for the model, as tuple (columns).
        parent -- An optional parent item.

        """
        self.parent = parent
        self._data = data
        self.children = []
        self._marks = []

    def data(self, column, role=Qt.DisplayRole):
        """Get the data for role/column.

        Raise ValueError if the role is invalid.

        """
        if role == Qt.DisplayRole:
            return self._data[column]
        elif role == Qt.UserRole:
            return self._marks
        else:
            raise ValueError

    def setdata(self, column, value, role=Qt.DisplayRole):
        """Set the data for column/role to value.

        Raise ValueError if the role is invalid.

        """
        if role == Qt.DisplayRole:
            self._data[column] = value
        elif role == Qt.UserRole:
            self._marks = value
        else:
            raise ValueError

    def column_count(self):
        """Return the column count in the item."""
        return len(self._data)

    def row(self):
        """Return the row index (int) of the item, or 0 if it's a root item."""
        if self.parent:
            return self.parent.children.index(self)
        return 0


class CompletionFilterModel(QSortFilterProxyModel):

    """Subclass of QSortFilterProxyModel with custom sorting/filtering."""

    _pattern = None
    srcmodel = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern = ''

    @property
    def pattern(self):
        """Getter for pattern."""
        return self._pattern

    def setsrc(self, model):
        """Set a new source model and clear the pattern.

        model -- The new source model.

        """
        self.setSourceModel(model)
        self.srcmodel = model
        self.pattern = ''

    @pattern.setter
    def pattern(self, val):
        """Setter for pattern.

        Invalidates the filter and re-sorts the model.

        If the current completion model overrides sort(), it is used.
        If not, the default implementation in QCompletionFilterModel is called.

        """
        self._pattern = val
        self.invalidateFilter()
        sortcol = 0
        srcmodel = self.sourceModel()
        if srcmodel is not None:
            try:
                srcmodel.sort(sortcol)
            except NotImplementedError:
                self.sort(sortcol)
            self.invalidate()

    def filterAcceptsRow(self, row, parent):
        """Custom filter implementation.

        Override QSortFilterProxyModel::filterAcceptsRow.

        row    -- The row of the item.
        parent -- The parent item QModelIndex.

        Return True if self.pattern is contained in item, or if it's a root
        item (category). Else returns False.

        """
        if parent == QModelIndex():
            return True
        idx = self.srcmodel.index(row, 0, parent)
        data = self.srcmodel.data(idx).value()
        # TODO more sophisticated filtering
        if not self.pattern:
            return True
        return self.pattern in data

    def lessThan(self, lindex, rindex):
        """Custom sorting implementation.

        lindex -- The QModelIndex of the left item (*left* < right)
        rindex -- The QModelIndex of the right item (left < *right*)

        Prefers all items which start with self.pattern. Other than that, uses
        normal Python string sorting.

        """
        left = self.srcmodel.data(lindex).value()
        right = self.srcmodel.data(rindex).value()

        leftstart = left.startswith(self.pattern)
        rightstart = right.startswith(self.pattern)

        if leftstart and rightstart:
            return left < right
        elif leftstart:
            return True
        elif rightstart:
            return False
        else:
            return left < right

    def first_item(self):
        """Return the first item in the model."""
        cat = self.index(0, 0)
        return self.index(0, 0, cat)

    def last_item(self):
        """Return the last item in the model."""
        cat = self.index(self.rowCount() - 1, 0)
        return self.index(self.rowCount(cat) - 1, 0, cat)
