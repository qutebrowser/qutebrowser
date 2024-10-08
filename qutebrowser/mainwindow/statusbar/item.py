from qutebrowser.browser.browsertab import AbstractTab
from qutebrowser.qt.widgets import QWidget


class StatusBarItem:
    def __init__(self, widget: QWidget):
        self.widget = widget

    def enable(self):
        self.widget.show()

    def disable(self):
        self.widget.hide()

    def on_tab_changed(self, tab: AbstractTab):
        # subclasses may use this
        pass
