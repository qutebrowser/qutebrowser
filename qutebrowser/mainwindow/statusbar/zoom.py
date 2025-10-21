"""Zoom percentage displayed in the statusbar."""

from qutebrowser.mainwindow.statusbar import textbase

from qutebrowser.qt.core import pyqtSlot

class Zoom(textbase.TextBase):

    """Shows percentage indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("100%")

    @pyqtSlot(float)
    def on_zoom_changed(self, factor):
        percentage = int(100 * factor)
        self.setText(f"{percentage}%")

    def on_tab_changed(self, tab):
        """Update zoom when tab changed."""
        percentage = int(100 * tab.zoom.factor())

        self.setText(f"{percentage}%")
