# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""QtWebEngine web inspector inside a tab using QSplitter"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSplitter
from qutebrowser.browser.webengine import webview

class SplitInspector(QSplitter):

    """QtWebEngine web inspector inside a tab using QSplitter"""

    def __init__(self, main_webview):
        super().__init__(Qt.Horizontal)
        self.addWidget(main_webview)
        inspector = webview.WebEngineView(tabdata=main_webview._tabdata,
                                          win_id=main_webview._win_id,
                                          private=main_webview._private)
        inspector.page().setInspectedPage(main_webview.page())
        self.addWidget(inspector)
        inspector.hide()

        self.inspector = inspector
        self.main_idx = 0
        self.inspector_idx = 1
        self.splitterMoved.connect(self._onSplitterMoved)

        self.preferredSize = max(300, self.width() / 2)
        self.setStretchFactor(self.main_idx,      1)
        self.setStretchFactor(self.inspector_idx, 0)

    def toggle(self, page):
        """Show/hide the inspector."""
        if self.inspector.isVisible():
            self.inspector.hide()
        else:
            self.show()

    def show(self):
        """Show the inspector."""
        if not self.inspector.isVisible():
            self.inspector.show()
            width = self.width()
            sizes = self.sizes()
            self._adjust_size()

    def resizeEvent(self, e):
        """Window resize event"""
        super().resizeEvent(e)
        if self.inspector.isVisible():
            self._adjust_size()

    def _adjust_size(self):
        sizes = self.sizes()
        total = sizes[0] + sizes[1]
        protected_main_size = 150
        if total >= self.preferredSize + protected_main_size and sizes[self.inspector_idx] != self.preferredSize:
            sizes[self.inspector_idx] = self.preferredSize
            sizes[self.main_idx] = total - self.preferredSize
            self.setSizes(sizes)
        if sizes[self.main_idx] < protected_main_size and total >= 300:
            sizes[self.main_idx] = protected_main_size
            sizes[self.inspector_idx] = total - protected_main_size
            self.setSizes(sizes)

    def _onSplitterMoved(self, pos, index):
        sizes = self.sizes()
        self.preferredSize = sizes[self.inspector_idx]
