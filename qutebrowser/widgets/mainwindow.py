from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from qutebrowser.widgets.statusbar.statusbar import StatusBar
from qutebrowser.widgets.browser import TabbedBrowser

class MainWindow(QMainWindow):
    """The main window of QuteBrowser"""
    cwidget = None
    vbox = None
    tabs = None
    status = None

    def __init__(self):
        super().__init__()

        self.setWindowTitle('qutebrowser')

        self.cwidget = QWidget(self)
        self.setCentralWidget(self.cwidget)

        self.vbox = QVBoxLayout(self.cwidget)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(0)

        self.tabs = TabbedBrowser(self)
        self.vbox.addWidget(self.tabs)

        self.status = StatusBar(self)
        self.vbox.addWidget(self.status)

        self.tabs.cur_progress.connect(self.status.prog.set_progress)
        self.tabs.cur_load_finished.connect(self.status.prog.load_finished)
        self.tabs.cur_scroll_perc_changed.connect(self.status.txt.set_perc)
        self.status.cmd.esc_pressed.connect(self.tabs.setFocus)

        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)
