from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtCore import Qt

class TabWidget(QTabWidget):
    """The tabwidget used for TabbedBrowser"""

    _stylesheet = """
        QTabWidget::pane {
            position: absolute;
            top: 0px;
        }

        QTabBar {
            font-family: Monospace, Courier;
            font-size: 8pt;
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
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet(self._stylesheet.strip())
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)
