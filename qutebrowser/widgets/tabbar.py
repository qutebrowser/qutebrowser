from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtCore import Qt

class TabWidget(QTabWidget):
    """The tabwidget used for TabbedBrowser"""

    # FIXME there is still some ugly 1px white stripe from somewhere if we do
    # background-color: grey for QTabBar...

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

        QTabBar::tab:first, QTabBar::tab:middle {
            border-right: 1px solid white;
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
