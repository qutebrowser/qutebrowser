from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout

from qutebrowser.utils import utils


class KeyWidget(QWidget):

    """Widget displaying key presses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._label = QLabel(text="Waiting for keypress...")
        self._layout.addWidget(self._label)

    def keyPressEvent(self, e):
        self._label.setText(utils.keyevent_to_string(e))


app = QApplication([])
w = KeyWidget()
w.show()
app.exec_()
