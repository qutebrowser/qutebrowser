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

class SplitInspector():

    """QtWebEngine web inspector inside a tab using QSplitter"""

    def __init__(self, main_webview):
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(main_webview)
        inspector = webview.WebEngineView(tabdata=main_webview._tabdata,
                                          win_id=main_webview._win_id,
                                          private=main_webview._private)
        inspector.page().setInspectedPage(main_webview.page())
        splitter.addWidget(inspector)
        inspector.hide()

        self.splitter = splitter
        self.inspector = inspector

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
            width = self.splitter.width()
            if self.splitter.sizes()[1] == 0:
                self.splitter.setSizes([width * 2 / 3, width / 3])
            self.splitter.setStretchFactor(0, 1)
            self.splitter.setStretchFactor(1, 0)
