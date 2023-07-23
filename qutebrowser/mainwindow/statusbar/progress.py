# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The progress bar in the statusbar."""

from qutebrowser.qt.core import pyqtSlot, QSize
from qutebrowser.qt.widgets import QProgressBar, QSizePolicy

from qutebrowser.config import stylesheet
from qutebrowser.utils import utils, usertypes


class Progress(QProgressBar):

    """The progress bar part of the status bar."""

    STYLESHEET = """
        QProgressBar {
            border-radius: 0px;
            border: 2px solid transparent;
            background-color: transparent;
            font: {{ conf.fonts.statusbar }};
        }

        QProgressBar::chunk {
            background-color: {{ conf.colors.statusbar.progress.bg }};
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        stylesheet.set_register(self)
        self.enabled = False
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setTextVisible(False)
        self.hide()

    def __repr__(self):
        return utils.get_repr(self, value=self.value())

    @pyqtSlot()
    def on_load_started(self):
        """Clear old error and show progress, used as slot to loadStarted."""
        self.setValue(0)
        self.setVisible(self.enabled)

    @pyqtSlot(int)
    def on_load_progress(self, value):
        """Hide the statusbar when loading finished.

        We use this instead of loadFinished because we sometimes get
        loadStarted and loadProgress(100) without loadFinished from Qt.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-65223
        """
        self.setValue(value)
        if value == 100:
            self.hide()

    def on_tab_changed(self, tab):
        """Set the correct value when the current tab changed."""
        self.setValue(tab.progress())
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
