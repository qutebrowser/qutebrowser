from collections import OrderedDict

from PyQt5.QtCore import (QAbstractItemModel, Qt, QModelIndex, QVariant,
                          QSortFilterProxyModel, pyqtSignal)


class CompletionModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = OrderedDict()
        self.parents = []
        self.root = CompletionItem([""] * 2)

    def removeRows(self, position=0, count=1, parent=QModelIndex()):
        node = self.node(parent)
        self.beginRemoveRows(parent, position, position + count - 1)
        node.children.pop(position)
        self.endRemoveRows()

    def node(self, index):
        if index.isValid():
            return index.internalPointer()
        else:
            return self.root

    def columnCount(self, parent=QModelIndex()):
        # pylint: disable=unused-argument
        return self.root.column_count()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        item = index.internalPointer()
        try:
            return QVariant(item.data(index.column(), role))
        except (IndexError, ValueError):
            return QVariant()

    def flags(self, index):
        # FIXME categories are not selectable, but moving via arrow keys still
        # tries to select them
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsEnabled
        if len(index.internalPointer().children) > 0:
            return flags
        else:
            return flags | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.root.data(section))
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        item = index.internalPointer()
        try:
            item.setdata(index.column(), value, role)
        except (IndexError, ValueError):
            return False
        self.dataChanged.emit(index, index)
        return True

    def index(self, row, column, parent=QModelIndex()):
        if (0 <= row < self.rowCount(parent) and
                0 <= column < self.columnCount(parent)):
            pass
        else:
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.children[row]
        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        item = index.internalPointer().parent
        if item == self.root or item is None:
            return QModelIndex()
        return self.createIndex(item.row(), 0, item)

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            pitem = self.root
        else:
            pitem = parent.internalPointer()

        return len(pitem.children)

    def sort(self, column, order=Qt.AscendingOrder):
        raise NotImplementedError

    def init_data(self):
        for (cat, items) in self._data.items():
            newcat = CompletionItem([cat], self.root)
            self.root.children.append(newcat)
            for item in items:
                newitem = CompletionItem(item, newcat)
                newcat.children.append(newitem)

    def mark_all_items(self, needle):
        for i in range(self.rowCount()):
            cat = self.index(i, 0)
            for k in range(self.rowCount(cat)):
                idx = self.index(k, 0, cat)
                old = self.data(idx).value()
                marks = self._get_marks(needle, old)
                self.setData(idx, marks, Qt.UserRole)

    def _get_marks(self, needle, haystack):
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
    parent = None
    _data = None
    children = None
    _marks = None

    def __init__(self, data, parent=None):
        self.parent = parent
        self._data = data
        self.children = []
        self._marks = []

    def data(self, column, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self._data[column]
        elif role == Qt.UserRole:
            return self._marks
        else:
            raise ValueError

    def setdata(self, column, value, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            self._data[column] = value
        elif role == Qt.UserRole:
            self._marks = value
        else:
            raise ValueError

    def column_count(self):
        return len(self._data)

    def row(self):
        if self.parent:
            return self.parent.children.index(self)
        return 0


class CompletionFilterModel(QSortFilterProxyModel):
    _pattern = None
    pattern_changed = pyqtSignal(str)

    @property
    def pattern(self):
        return self._pattern

    @pattern.setter
    def pattern(self, val):
        self._pattern = val
        self.invalidate()
        self.pattern_changed.emit(val)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pattern = ''

    def filterAcceptsRow(self, row, parent):
        if parent == QModelIndex():
            return True
        idx = self.sourceModel().index(row, 0, parent)
        data = self.sourceModel().data(idx).value()
        # TODO more sophisticated filtering
        if not self.pattern:
            return True
        return self.pattern in data

    def lessThan(self, lindex, rindex):
        left = self.sourceModel().data(lindex).value()
        right = self.sourceModel().data(rindex).value()

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
        cat = self.index(0, 0)
        return self.index(0, 0, cat)

    def last_item(self):
        cat = self.index(self.rowCount() - 1, 0)
        return self.index(self.rowCount(cat) - 1, 0, cat)
