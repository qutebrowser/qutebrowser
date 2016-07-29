# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.utils import usertypes


Role = usertypes.enum('Role', ['sort', 'userdata'], start=Qt.UserRole,
                      is_int=True)


class BaseCompletionModel(QStandardItemModel):

    """A simple QStandardItemModel adopted for completions.

    Used for showing completions later in the CompletionView. Supports setting
    marks and adding new categories/items easily.

    Class Attributes:
        COLUMN_WIDTHS: The width percentages of the columns used in the
                        completion view.
        DUMB_SORT: the dumb sorting used by the model
    """

    COLUMN_WIDTHS = (30, 70, 0)
    DUMB_SORT = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.columns_to_filter = [0]

    def new_category(self, name, sort=None):
        """Add a new category to the model.

        Args:
            name: The name of the category to add.
            sort: The value to use for the sort role.

        Return:
            The created QStandardItem.
        """
        cat = QStandardItem(name)
        if sort is not None:
            cat.setData(sort, Role.sort)
        self.appendRow(cat)
        return cat

    def new_item(self, cat, name, desc='', misc=None, sort=None,
                 userdata=None):
        """Add a new item to a category.

        Args:
            cat: The parent category.
            name: The name of the item.
            desc: The description of the item.
            misc: Misc text to display.
            sort: Data for the sort role (int).
            userdata: User data to be added for the first column.

        Return:
            A (nameitem, descitem, miscitem) tuple.
        """
        assert not isinstance(name, int)
        assert not isinstance(desc, int)
        assert not isinstance(misc, int)

        nameitem = QStandardItem(name)
        descitem = QStandardItem(desc)
        if misc is None:
            miscitem = QStandardItem()
        else:
            miscitem = QStandardItem(misc)

        cat.appendRow([nameitem, descitem, miscitem])
        if sort is not None:
            nameitem.setData(sort, Role.sort)
        if userdata is not None:
            nameitem.setData(userdata, Role.userdata)
        return nameitem, descitem, miscitem

    def delete_cur_item(self, win_id):
        """Delete the selected item."""
        raise NotImplementedError

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
