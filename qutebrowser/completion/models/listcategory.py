# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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
from PyQt5.QtGui import QStandardItem, QStandardItemModel


class ListCategory(QStandardItemModel):

    """Expose a list of items as a category for the CompletionModel."""

    def __init__(self, name, items, parent=None):
        super().__init__(parent)
        self.name = name
        # self.setColumnCount(3) TODO needed?
        # TODO: batch insert?
        # TODO: can I just insert a tuple instead of a list?
        for item in items:
            self.appendRow([QStandardItem(x) for x in item])

    def flags(self, index):
        """Return the item flags for index.

        Override QAbstractItemModel::flags.

        Args:
            index: The QModelIndex to get item flags for.

        Return:
            The item flags, or Qt.NoItemFlags on error.
        """
        if not index.isValid():
            return

        if index.parent().isValid():
            # item
            return (Qt.ItemIsEnabled | Qt.ItemIsSelectable |
                    Qt.ItemNeverHasChildren)
        else:
            # category
            return Qt.NoItemFlags

    def set_pattern(self, pattern):
        pass
