from PyQt5.QtWidgets import QLineEdit, QHBoxLayout, QLabel

class StatusBar(QHBoxLayout):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)

        self.cmd = StatusCommand(parent)
        self.addWidget(self.cmd)

        self.lbl = StatusText(parent)
        self.addWidget(self.lbl)

class StatusText(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet('QLabel { background: yellow }')

class StatusCommand(QLineEdit):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet('QLineEdit { background: yellow }')
