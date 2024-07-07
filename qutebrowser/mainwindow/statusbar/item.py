from qutebrowser.qt.widgets import QWidget


class StatusBarItem:
    def __init__(self, widget: QWidget):
        self.widget = widget

    def enable(self):
        self.widget.show()

    def disable(self):
        self.widget.hide()
