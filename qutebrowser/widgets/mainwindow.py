"""The main window of QuteBrowser."""

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from qutebrowser.widgets.statusbar import StatusBar
from qutebrowser.widgets.browser import TabbedBrowser
from qutebrowser.widgets.completion import CompletionView


class MainWindow(QMainWindow):

    """The main window of QuteBrowser.

    Adds all needed components to a vbox, initializes subwidgets and connects
    signals.

    """

    cwidget = None
    vbox = None
    tabs = None
    status = None

    def __init__(self):
        super().__init__()

        self.setWindowTitle('qutebrowser')
        # FIXME maybe store window position/size on exit
        self.resize(800, 600)

        self.cwidget = QWidget(self)
        self.setCentralWidget(self.cwidget)

        self.vbox = QVBoxLayout(self.cwidget)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(0)

        self.tabs = TabbedBrowser(self)
        self.vbox.addWidget(self.tabs)

        self.completion = CompletionView(self)

        self.status = StatusBar(self)
        self.vbox.addWidget(self.status)

        self.status.resized.connect(self.completion.resize_to_bar)
        self.status.moved.connect(self.completion.move_to_bar)
        self.tabs.cur_progress.connect(self.status.prog.set_progress)
        self.tabs.cur_load_finished.connect(self.status.prog.load_finished)
        self.tabs.cur_load_started.connect(lambda:
                                           self.status.prog.set_progress(0))
        self.tabs.cur_scroll_perc_changed.connect(self.status.txt.set_perc)
        self.tabs.cur_statusbar_message.connect(self.status.txt.set_text)
        self.tabs.cur_url_changed.connect(self.status.txt.set_url)
        self.status.cmd.esc_pressed.connect(self.tabs.setFocus)
        self.status.cmd.hide_completion.connect(self.completion.hide)
        self.status.cmd.textChanged.connect(self.completion.cmd_text_changed)
        self.status.cmd.tab_pressed.connect(self.completion.tab_handler)
        self.completion.append_cmd_text.connect(self.status.cmd.append_cmd)

        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)
