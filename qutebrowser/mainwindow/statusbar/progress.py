# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The progress bar in the statusbar."""

from qutebrowser.mainwindow.statusbar.item import StatusBarItem
from qutebrowser.qt.core import QSize
from qutebrowser.qt.widgets import QProgressBar, QSizePolicy

from qutebrowser.config import stylesheet
from qutebrowser.utils import utils, usertypes


class ProgressWidget(QProgressBar):

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

    def __repr__(self):
        return utils.get_repr(self, value=self.value())

    def sizeHint(self):
        """Set the height to the text height."""
        width = super().sizeHint().width()
        height = self.fontMetrics().height()
        return QSize(width, height)

    def minimumSizeHint(self):
        return self.sizeHint()


class Progress(StatusBarItem):
    def __init__(self, widget: ProgressWidget):
        super().__init__(widget)
        self.enabled = False
        stylesheet.set_register(self.widget)
        self.widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.widget.setTextVisible(False)
        self.widget.hide()

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def on_load_started(self):
        """Clear old error and show progress, used as slot to loadStarted."""
        self.widget.setValue(0)
        self.widget.setVisible(self.enabled)

    def on_tab_changed(self, tab):
        """Set the correct value when the current tab changed."""
        self.widget.setValue(tab.progress())
        if self.enabled and tab.load_status() == usertypes.LoadStatus.loading:
            self.widget.show()
        else:
            self.widget.hide()

    def on_load_progress(self, value):
        """Hide the statusbar when loading finished.

        We use this instead of loadFinished because we sometimes get
        loadStarted and loadProgress(100) without loadFinished from Qt.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-65223
        """
        self.widget.setValue(value)
        if value == 100:
            self.widget.hide()
