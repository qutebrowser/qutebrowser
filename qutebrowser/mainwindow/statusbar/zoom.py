"""Zoom percentage displayed in the statusbar."""

from qutebrowser.browser import browsertab
from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.qt.core import pyqtSlot, QObject
from qutebrowser.config import config


class Zoom(textbase.TextBase):

    """Shows zoom percentage in current tab."""

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self.on_zoom_changed(1)

    @pyqtSlot(float)
    def on_zoom_changed(self, factor: float) -> None:
        """Update percentage when factor changed."""
        if factor == 1 and config.val.statusbar.zoom.show == 'non-default':
            self.hide()
            return
        self.show()
        percentage = round(100 * factor)
        self.setText(f"[{percentage}%]")

    def on_tab_changed(self, tab: browsertab.AbstractTab) -> None:
        """Update percentage when tab changed."""
        self.on_zoom_changed(tab.zoom.factor())
