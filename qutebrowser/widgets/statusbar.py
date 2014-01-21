import logging

from PyQt5.QtWidgets import (QLineEdit, QHBoxLayout, QLabel, QWidget,
                             QShortcut, QProgressBar, QSizePolicy)
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QValidator, QKeySequence

class StatusBar(QWidget):
    """The statusbar at the bottom of the mainwindow"""
    has_error = False # Statusbar is currently in error mode
    hbox = None
    cmd = None
    txt = None
    prog = None

    # TODO: the statusbar should be a bit smaller
    def __init__(self, parent):
        super().__init__(parent)
        self.set_color("white", "black")
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.setSpacing(0)

        self.cmd = StatusCommand(self)
        self.hbox.addWidget(self.cmd)

        self.txt = StatusText(self)
        self.hbox.addWidget(self.txt)

        self.prog = StatusProgress(self)
        self.hbox.addWidget(self.prog)

    def set_color(self, fg, bg):
        """Sets background and foreground color of the statusbar"""
        # FIXME maybe this would be easier with setColor()?

        self.setStyleSheet("""
            * {
                background: """ + bg + """;
                color: """ + fg + """;
                font-family: Monospace, Courier;
            }""")

    def disp_error(self, text):
        """Displays an error in the statusbar"""
        self.has_error = True
        self.set_color('white', 'red')
        self.txt.error = text

    def clear_error(self):
        """Clears a displayed error from the status bar"""
        if self.has_error:
            self.has_error = False
            self.set_color('white', 'black')
            self.txt.error = ''

class StatusProgress(QProgressBar):
    """ The progress bar part of the status bar"""
    bar = None

    def __init__(self, bar):
        self.bar = bar
        super().__init__(bar)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setTextVisible(False)
        self.setStyleSheet("""
            QProgressBar {
                border-radius: 0px;
                border: 2px solid transparent;
                margin-left: 1px;
            }

            QProgressBar::chunk {
                background-color: white;
            }
        """)
        self.hide()

    def minimumSizeHint(self):
        status_size = self.bar.size()
        return QSize(100, status_size.height())

    def sizeHint(self):
        return self.minimumSizeHint()

    def set_progress(self, prog):
        """Sets the progress of the bar and shows/hides it if necessary"""
        # TODO display failed loading in some meaningful way?
        if prog == 100:
            self.setValue(prog)
            self.hide()
        else:
            self.setValue(prog)
            self.show()

    def load_finished(self, ok):
        self.hide()

class StatusText(QLabel):
    """The text part of the status bar, composed of several 'widgets'"""
    keystring = ''
    error = ''
    text = ''
    scrollperc = ''

    def __init__(self, bar):
        super().__init__(bar)
        self.setStyleSheet("padding-right: 1px")

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        self.update()

    def set_keystring(self, s):
        """Setter to be used as a Qt slot"""
        self.keystring = s

    def set_perc(self, x, y):
        """Setter to be used as a Qt slot"""
        if y == 0:
            # FIXME  we currently get the _top_ of the frame position, so this
            # will never happen
            self.scrollperc = '[top]'
        else:
            self.scrollperc = '[{}%]'.format(y)

    def update(self):
        """Update the text displayed"""
        self.setText(' '.join([self.keystring, self.error, self.text,
                               self.scrollperc]))


class StatusCommand(QLineEdit):
    """The commandline part of the statusbar"""
    class CmdValidator(QValidator):
        """Validator to prevent the : from getting deleted"""
        def validate(self, string, pos):
            if string.startswith(':'):
                return (QValidator.Acceptable, string, pos)
            else:
                return (QValidator.Invalid, string, pos)

    got_cmd = pyqtSignal(str) # Emitted when a command is triggered by the user
    bar = None # The status bar object
    esc_pressed = pyqtSignal() # Emitted when escape is pressed
    esc = None # The esc QShortcut object

    def __init__(self, bar):
        super().__init__(bar)
        self.bar = bar
        self.setStyleSheet("border: 0px; padding-left: 1px")
        self.setValidator(self.CmdValidator())
        self.returnPressed.connect(self.process_cmd)

        self.esc = QShortcut(self)
        self.esc.setKey(QKeySequence(Qt.Key_Escape))
        self.esc.setContext(Qt.WidgetWithChildrenShortcut)
        self.esc.activated.connect(self.esc_pressed)

    def process_cmd(self):
        """Handle the command in the status bar"""
        text = self.text().lstrip(':')
        self.setText('')
        self.got_cmd.emit(text)

    def set_cmd(self, text):
        """Preset the statusbar to some text"""
        self.setText(text)
        self.setFocus()

    def focusOutEvent(self, e):
        """Clear the statusbar text if it's explicitely unfocused"""
        if e.reason() in [Qt.MouseFocusReason, Qt.TabFocusReason,
                          Qt.BacktabFocusReason, Qt.OtherFocusReason]:
            self.setText('')
        super().focusOutEvent(e)

    def focusInEvent(self, e):
        """Clear error message when the statusbar is focused"""
        self.bar.clear_error()
        super().focusInEvent(e)

