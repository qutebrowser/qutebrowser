from PyQt5.QtWidgets import QLineEdit, QHBoxLayout, QLabel, QWidget, QShortcut, QProgressBar, QSizePolicy
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QValidator, QKeySequence

class StatusBar(QWidget):
    has_error = False
    parent = None

    # TODO: the statusbar should be a bit smaller
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName(self.__class__.__name__)
        self.set_color("white", "black")
        self.hbox = QHBoxLayout(self)
        self.hbox.setObjectName("status_hbox")
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.setSpacing(0)

        self.cmd = StatusCommand(self)
        self.hbox.addWidget(self.cmd)

        self.lbl = StatusText(self)
        self.hbox.addWidget(self.lbl)

        self.prog = StatusProgress(self)
        self.hbox.addWidget(self.prog)

    def set_color(self, fg, bg):
        self.setStyleSheet("""
            * {
                background: """ + bg + """;
                color: """ + fg + """;
                font-family: Monospace, Courier;
            }""")

    def disp_error(self, text):
        self.has_error = True
        self.set_color('white', 'red')
        self.lbl.disp_error(text)

    def clear_error(self):
        if self.has_error:
            self.has_error = False
            self.set_color('white', 'black')
            self.lbl.clear_error()

class StatusProgress(QProgressBar):
    parent = None

    def __init__(self, parent):
        self.parent = parent
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)

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
        status_size = self.parent.size()
        return QSize(100, status_size.height())

    def sizeHint(self):
        return self.minimumSizeHint()

    def set_progress(self, prog):
        if prog == 100:
            self.setValue(prog)
            self.hide()
        else:
            self.setValue(prog)
            self.show()

    def load_finished(self, ok):
        self.hide()

class StatusText(QLabel):
    pre_error_text = None

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet("padding-right: 1px")

    def disp_error(self, text):
        txt = self.text()
        self.pre_error_text = self.text()
        self.setText('Error: {}'.format(text))

    def clear_error(self):
        if self.pre_error_text is not None:
            self.setText(self.pre_error_text)

class StatusCommand(QLineEdit):
    got_cmd = pyqtSignal(str)
    parent = None

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet("border: 0px; padding-left: 1px")
        self.setValidator(CmdValidator())
        self.returnPressed.connect(self.process_cmd)

        self.esc = QShortcut(self)
        self.esc.setKey(QKeySequence(Qt.Key_Escape))
        self.esc.setContext(Qt.WidgetWithChildrenShortcut)
        # FIXME this is fugly and doesn't clear the keystring
        self.esc.activated.connect(parent.parent.tabs.setFocus)

    def process_cmd(self):
        text = self.text().lstrip(':')
        self.setText('')
        self.got_cmd.emit(text)

    def set_cmd(self, text):
        self.setText(text)
        self.setFocus()

    def focusOutEvent(self, e):
        if e.reason() in [Qt.MouseFocusReason, Qt.TabFocusReason,
                Qt.BacktabFocusReason, Qt.OtherFocusReason]:
            self.setText('')
        super().focusOutEvent(e)

    def focusInEvent(self, event):
        self.parent.clear_error()
        super().focusInEvent(event)

class CmdValidator(QValidator):
    def validate(self, string, pos):
        if string.startswith(':'):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)
