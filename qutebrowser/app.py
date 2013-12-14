import sys
from PyQt5.QtWidgets import QApplication, QWidget
from qutebrowser.widgets import CommandEdit

class TestWindow(QWidget):
    def __init__(self):
        super(TestWindow, self).__init__()
        self.ce = CommandEdit(self)
        self.ce.move(0, 0)
        self.resize(self.ce.sizeHint())
        self.show()

def main():
    app = QApplication(sys.argv)
    tw = TestWindow()
    sys.exit(app.exec_())
