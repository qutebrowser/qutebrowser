# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""CompletionModels for URLs."""

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QStandardItem

from qutebrowser.utils import objreg
from qutebrowser.completion.models import base


class UrlCompletionModel(base.BaseCompletionModel):

    """A model which combines quickmarks and web history URLs.

    Used for the `open` command."""

    # pylint: disable=abstract-method

    def __init__(self, parent=None):
        super().__init__(parent)

        self._quickmark_cat = self.new_category("Quickmarks")
        self._history_cat = self.new_category("History")

        quickmarks = objreg.get('quickmark-manager').marks.items()
        self._history = objreg.get('web-history')

        for qm_name, qm_url in quickmarks:
            self.new_item(self._quickmark_cat, qm_url, qm_name)

        for entry in self._history:
            atime = int(entry.atime)
            self.new_item(self._history_cat, entry.url, "", str(atime),
                          sort=atime)

        self._history.item_added.connect(self.on_history_item_added)

    @pyqtSlot(object)
    def on_history_item_added(self, item):
        """Slot called when a new history item was added."""
        if item.url:
            atime = int(item.atime)
            if self._history.historyContains(item.url):
                for i in range(self._history_cat.rowCount()):
                    name = self._history_cat.child(i, 0)
                    if not name:
                        continue
                    if name.text() == item.url:
                        self._history_cat.setChild(i, 2,
                                                   QStandardItem(str(atime)))
                        name.setData(str(atime), base.Role.sort)
                        break
            else:
                self.new_item(self._history_cat, item.url, "", str(atime),
                              sort=atime)
