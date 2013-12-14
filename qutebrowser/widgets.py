from PyQt5.QtWidgets import QLineEdit, QHBoxLayout, QLabel, QWidget, QTabWidget

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
        self.setStyleSheet("""* {{ background: {}; color: white; font-family:
                Monospace; }}""".format(color))

class StatusText(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet("padding-right: 1px")

class StatusCommand(QLineEdit):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet("border: 0px; padding-left: 1px")

class TabWidget(QTabWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet("""
            QTabWidget::pane {
                position: absolute;
                top: 0px;
            }

            QTabBar::tab {
                background-color: grey;
                color: white;
                padding-left: 5px;
                padding-right: 5px;
                padding-top: 0px;
                padding-bottom: 0px;
            }

            QTabBar::tab:selected {
                background-color: black;
            }
        """)
