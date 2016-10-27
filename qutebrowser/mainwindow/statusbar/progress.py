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

"""The progress bar in the statusbar."""

from PyQt5.QtCore import pyqtSlot, QSize
from PyQt5.QtWidgets import QProgressBar, QSizePolicy

from qutebrowser.browser import browsertab
from qutebrowser.config import style
from qutebrowser.utils import utils, usertypes


class Progress(QProgressBar):

    """The progress bar part of the status bar."""

    STYLESHEET = """
        QProgressBar {
            border-radius: 0px;
            border: 2px solid transparent;
            background-color: transparent;
            font: {{ font['statusbar'] }};
        }

        QProgressBar::chunk {
            background-color: {{ color['statusbar.progress.bg'] }};
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        style.set_register_stylesheet(self)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setTextVisible(False)
        self.hide()

    def __repr__(self):
        return utils.get_repr(self, value=self.value())

    @pyqtSlot()
    def on_load_started(self):
        """Clear old error and show progress, used as slot to loadStarted."""
        self.setValue(0)
        self.show()

    @pyqtSlot(browsertab.AbstractTab)
    def on_tab_changed(self, tab):
        """Set the correct value when the current tab changed."""
        if self is None:  # pragma: no branch
            # This should never happen, but for some weird reason it does
            # sometimes.
            return  # pragma: no cover
        self.setValue(tab.progress())
        if tab.load_status() == usertypes.LoadStatus.loading:
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
