# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""The progress bar in the statusbar."""

from PyQt5.QtCore import pyqtSlot, QSize
from PyQt5.QtWidgets import QLabel, QSizePolicy

from qutebrowser.config import stylesheet
from qutebrowser.utils import utils, usertypes


class Progress(QLabel):

    """The ascii progress bar part of the status bar."""

    STYLESHEET = """
        QLabel {
            font: {{ conf.fonts.statusbar }};
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        stylesheet.set_register(self)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.enabled = False
        self.chunks = 10
        self.value = 0

        self.update_bar(self.value)
        self.hide()

    def __repr__(self):
        return utils.get_repr(self, value=self.value)

    def update_bar(self, val: int) -> None:
        """Update the value of the progress bar."""
        self.value = val
        c = self.value//self.chunks
        bar = f"{'=' * (c - 1)}{'>' * (c > 0)}{' '*(self.chunks - c)}"
        self.setText(f"[{bar}]")

    @pyqtSlot()
    def on_load_started(self):
        """Reset the value, and show the bar if enabled. Used as slot to loadStarted."""
        self.update_bar(0)
        self.setVisible(self.enabled)

    @pyqtSlot(int)
    def on_load_progress(self, value: int):
        """Hide the statusbar when loading finished.

        We use this instead of loadFinished because we sometimes get
        loadStarted and loadProgress(100) without loadFinished from Qt.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-65223
        """
        self.update_bar(value)
        if value == 100:
            self.hide()

    def on_tab_changed(self, tab):
        """Set the correct value when the current tab changed."""
        self.update_bar(tab.progress())
        if self.enabled and tab.load_status() == usertypes.LoadStatus.loading:
            self.show()
        else:
            self.hide()

    def sizeHint(self):
        """Set the height to the text height."""
        width = super().sizeHint().width()
        height = self.fontMetrics().height()
        return QSize(width, height)

    def minimumSizeHint(self):
        return self.sizeHint()
