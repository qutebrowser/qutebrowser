"""The tab widget used for TabbedBrowser from browser.py."""

from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtCore import Qt

import qutebrowser.utils.config as config


class TabWidget(QTabWidget):
    """The tabwidget used for TabbedBrowser."""

    # FIXME there is still some ugly 1px white stripe from somewhere if we do
    # background-color: grey for QTabBar...

    _stylesheet = """
        QTabWidget::pane {{
            position: absolute;
            top: 0px;
        }}

        QTabBar {{
            font-family: {monospace};
            font-size: 8pt;
        }}

        QTabBar::tab {{
            {color[tab.bg]}
            {color[tab.fg]}
            padding-left: 5px;
            padding-right: 5px;
            padding-top: 0px;
            padding-bottom: 0px;
        }}

        QTabBar::tab:first, QTabBar::tab:middle {{
            border-right: 1px solid {color[tab.seperator]};
        }}

        QTabBar::tab:selected {{
            {color[tab.bg.selected]}
        }}
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))
        self.setDocumentMode(True)
        self.setElideMode(Qt.ElideRight)
