from PyQt5.QtWidgets import QLineEdit, QHBoxLayout, QLabel, QWidget
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QValidator

class StatusBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.bg_color("black")
        self.hbox = QHBoxLayout(self)
        self.hbox.setObjectName("status_hbox")
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.setSpacing(0)

        self.cmd = StatusCommand(self)
        self.hbox.addWidget(self.cmd)

        self.lbl = StatusText(self)
        self.hbox.addWidget(self.lbl)

    def bg_color(self, color):
        self.setStyleSheet("""
            * {
                background: """ + color + """;
                color: white;
                font-family: Monospace;
            }""")

class StatusText(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet("padding-right: 1px")

class StatusCommand(QLineEdit):
    got_cmd = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet("border: 0px; padding-left: 1px")
        self.setValidator(CmdValidator())
        self.returnPressed.connect(self.process_cmd)

    def process_cmd(self):
        text = self.text().lstrip(':')
        self.setText('')
        self.got_cmd.emit(text)

class CmdValidator(QValidator):
    def validate(self, string, pos):
        if string.startswith(':'):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)
