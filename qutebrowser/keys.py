from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence

class KeyParser(QObject):
    set_cmd_text = pyqtSignal(str)
    id_to_cmd = {}

    def from_cmd_dict(self, d, parent):
        for cmd in d.values():
            if cmd.key is not None:
                sc = QShortcut(parent)
                sc.setKey(QKeySequence(cmd.key))
                sc.setContext(Qt.WidgetWithChildrenShortcut)
                sc.activated.connect(self.handle)
                self.id_to_cmd[sc.id()] = cmd

    def handle(self):
        cmd = self.id_to_cmd[self.sender().id()]
        text = ':' + cmd.name
        if cmd.nargs and cmd.nargs != 0:
            text += ' '
        self.set_cmd_text.emit(text)
