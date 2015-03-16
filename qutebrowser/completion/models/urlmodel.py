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

import datetime

from PyQt5.QtCore import pyqtSlot

from qutebrowser.utils import objreg, utils
from qutebrowser.completion.models import base
from qutebrowser.config import config


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

        max_history = config.get('completion', 'web-history-max-items')
        history = utils.newest_slice(self._history, max_history)

        for entry in history:
            self.new_item(self._history_cat, entry.url.toDisplayString(), "",
                          self._fmt_atime(entry.atime), sort=int(entry.atime))

        self._history.item_about_to_be_added.connect(
            self.on_history_item_added)
        objreg.get('config').changed.connect(self.reformat_timestamps)

    def _fmt_atime(self, atime):
        """Format an atime to a human-readable string."""
        fmt = config.get('completion', 'timestamp-format')
        if fmt is None:
            return ''
        return datetime.datetime.fromtimestamp(atime).strftime(fmt)

    @config.change_filter('completion', 'timestamp-format')
    def reformat_timestamps(self):
        """Reformat the timestamps if the config option was changed."""
        for i in range(self._history_cat.rowCount()):
            name_item = self._history_cat.child(i, 0)
            atime_item = self._history_cat.child(i, 2)
            atime = name_item.data(base.Role.sort)
            atime_item.setText(self._fmt_atime(atime))

    @pyqtSlot(object)
    def on_history_item_added(self, item):
        """Slot called when a new history item was added."""
        if item.url:
            if self._history.historyContains(item.url_string):
                for i in range(self._history_cat.rowCount()):
                    name_item = self._history_cat.child(i, 0)
                    atime_item = self._history_cat.child(i, 2)
                    if not name_item:
                        continue
                    if name_item.text() == item.url:
                        atime_item.setText(self._fmt_atime(item.atime))
                        name_item.setData(int(item.atime), base.Role.sort)
                        break
            else:
                self.new_item(self._history_cat, item.url.toDisplayString(),
                              "", self._fmt_atime(item.atime),
                              sort=int(item.atime))
