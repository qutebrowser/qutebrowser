from PyQt5.QtWidgets import QTabWidget

class TabWidget(QTabWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet("""
            QTabWidget::pane {
                position: absolute;
                top: 0px;
            }

            QTabBar {
                font-family: Monospace;
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
        self.setDocumentMode(True)
