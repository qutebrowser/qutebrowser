# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The progress bar in the statusbar."""

from qutebrowser.qt.core import pyqtSlot, QSize, Qt
from qutebrowser.qt.widgets import QProgressBar, QSizePolicy
from qutebrowser.qt.gui import QPainter, QColor
from qutebrowser.config import stylesheet, config
from qutebrowser.utils import utils, usertypes

class Progress(QProgressBar):
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
        self.setValue(0)
        self.setVisible(self.enabled)

    @pyqtSlot(int)
    def on_load_progress(self, value):
        self.setValue(value)
        if value == 100:
            self.hide()

    def on_tab_changed(self, tab):
        self.setValue(tab.progress())
        if self.enabled and tab.load_status() == usertypes.LoadStatus.loading:
            self.show()
        else:
            self.hide()

    def sizeHint(self):
        style = getattr(config.val.statusbar.progress, 'style', 'default')
        if style == 'ascii':
            return QSize(self.fontMetrics().averageCharWidth() * 12, super().sizeHint().height())
        return super().sizeHint()

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        style = getattr(config.val.statusbar.progress, 'style', 'default')
        
        if style != 'ascii':
            super().paintEvent(event)
            return

        painter = QPainter(self)
        bg_color = QColor(config.val.colors.statusbar.normal.bg)
        fg_color = QColor(config.val.colors.statusbar.normal.fg)

        painter.fillRect(self.rect(), bg_color)
        painter.setPen(fg_color)

        pct = (self.value() - self.minimum()) / max(1, self.maximum() - self.minimum())
        filled = int(10 * pct)
        bar_content = ("=" * filled + ">").ljust(11)[:10]
        if pct >= 1: bar_content = "=" * 10 

        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"[{bar_content}]")
        painter.end()