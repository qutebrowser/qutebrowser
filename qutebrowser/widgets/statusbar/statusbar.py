import logging

from PyQt5.QtWidgets import QHBoxLayout, QWidget

from qutebrowser.widgets.statusbar.command import Command
from qutebrowser.widgets.statusbar.text import Text
from qutebrowser.widgets.statusbar.progress import Progress

class StatusBar(QWidget):
    """The statusbar at the bottom of the mainwindow"""
    hbox = None
    cmd = None
    txt = None
    prog = None
    fgcolor = 'white'
    bgcolor = 'black'
    font = 'Monospace, Courier'
    _stylesheet = """
        * {{
            background: {self.bgcolor};
            color: {self.fgcolor};
            font-family: {self.font};
        }}
    """

    def __setattr__(self, name, value):
        """Update the stylesheet if relevant attributes have been changed"""
        super().__setattr__(name, value)
        if name in ['fgcolor', 'bgcolor', 'font']:
            self.setStyleSheet(self._stylesheet.strip().format(self=self))

    # TODO: the statusbar should be a bit smaller
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet(self._stylesheet.strip().format(self=self))
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
        self.bgcolor = 'red'
        self.txt.error = text

    def clear_error(self):
        """Clears a displayed error from the status bar"""
        self.bgcolor = 'black'
        self.txt.error = ''


