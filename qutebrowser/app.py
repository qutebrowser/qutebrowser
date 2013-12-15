import sys
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow

def main():
    app = QApplication(sys.argv)

    mw = MainWindow()
    mw.show()

    sys.exit(app.exec_())
