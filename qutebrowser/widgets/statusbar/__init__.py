"""Several widgets in the statusbar."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QWidget

import qutebrowser.utils.config as config
from qutebrowser.widgets.statusbar.command import Command
from qutebrowser.widgets.statusbar.text import Text
from qutebrowser.widgets.statusbar.progress import Progress


class StatusBar(QWidget):
    """The statusbar at the bottom of the mainwindow"""
    hbox = None
    cmd = None
    txt = None
    prog = None
    resized = pyqtSignal('QRect')
    fgcolor = None
    bgcolor = None
    _stylesheet = """
        * {{
            {color[statusbar.bg.__cur__]}
            {color[statusbar.fg.__cur__]}
            font-family: {monospace};
        }}
    """

    def __setattr__(self, name, value):
        """Update the stylesheet if relevant attributes have been changed"""
        super().__setattr__(name, value)
        if name == 'fgcolor' and value is not None:
            config.colordict['statusbar.fg.__cur__'] = value
            self.setStyleSheet(config.get_stylesheet(self._stylesheet))
        elif name == 'bgcolor' and value is not None:
            config.colordict['statusbar.bg.__cur__'] = value
            self.setStyleSheet(config.get_stylesheet(self._stylesheet))

    # TODO: the statusbar should be a bit smaller
    def __init__(self, mainwindow):
        super().__init__(mainwindow)
        self.fgcolor = config.colordict.getraw('statusbar.fg')
        self.bgcolor = config.colordict.getraw('statusbar.bg')
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))

        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.setSpacing(0)

        self.cmd = Command(self)
        self.hbox.addWidget(self.cmd)

        self.txt = Text(self)
        self.hbox.addWidget(self.txt)

        self.prog = Progress(self)
        self.hbox.addWidget(self.prog)

    def disp_error(self, text):
        """Displays an error in the statusbar"""
        self.bgcolor = config.colordict.getraw('statusbar.bg.error')
        self.fgcolor = config.colordict.getraw('statusbar.fg.error')
        self.txt.error = text

    def clear_error(self):
        """Clears a displayed error from the status bar"""
        self.bgcolor = config.colordict.getraw('statusbar.bg')
        self.fgcolor = config.colordict.getraw('statusbar.fg')
        self.txt.error = ''

    def resizeEvent(self, e):
        """Override resizeEvent of QWidget to emit a resized signal afterwards.

        e -- The QResizeEvent.
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())
