"""Completion model for autocompleting flags in the :spawn command."""

from typing import Optional
from qutebrowser.qt.core import QAbstractListModel, Qt, QModelIndex, QVariant
from qutebrowser.completion.models import BaseCategory

class SpawnFlagsModel(QAbstractListModel, BaseCategory):
    """Completion model for flags used in :spawn commands."""

    def __init__(self, parent: Optional[QModelIndex] = None) -> None:
        super().__init__(parent)
        self._items = [
            ("--userscript", "Run as userscript"),
            ("--verbose", "Enable verbose output"),
            ("--output", "Set output path"),
            ("--output-messages", "Enable output messages"),
            ("--detach", "Run detached"),
            ("--count", "Specify repeat count"),
        ]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> QVariant:
        if not index.isValid() or index.row() >= len(self._items):
            return QVariant()
        item = self._items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return item[0]
        elif role == Qt.ItemDataRole.ToolTipRole:
            return item[1]
        return QVariant()
