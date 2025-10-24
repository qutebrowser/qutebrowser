"""Zoom percentage displayed in the statusbar."""

from qutebrowser.browser import browsertab
from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.qt.core import pyqtSlot, QObject


class Zoom(textbase.TextBase):

    """Shows zoom percentage in current tab."""

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self.setText("100%")

    @pyqtSlot(float)
    def on_zoom_changed(self, factor: float) -> None:
        """Update percentage when factor changed."""
        percentage = int(100 * factor)
        self.setText(f"{percentage}%")

    def on_tab_changed(self, tab: browsertab.AbstractTab) -> None:
        """Update percentage when tab changed."""
        percentage = int(100 * tab.zoom.factor())

        self.setText(f"{percentage}%")
