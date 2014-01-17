from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence
import logging

class KeyParser(QObject):
    keyparent = None
    set_cmd_text = pyqtSignal(str)
    id_to_cmd = {}

    def __init__(self, keyparent):
        super().__init__()
        self.keyparent = keyparent
        sc = QShortcut(keyparent)
        sc.setKey(QKeySequence(':'))
        sc.setContext(Qt.WidgetWithChildrenShortcut)
        sc.activated.connect(self.handle_empty)

    def from_cmd_dict(self, d):
        for cmd in d.values():
            if cmd.key is not None:
                logging.debug('registered: {} -> {}'.format(cmd.name, cmd.key))
                sc = QShortcut(self.keyparent)
                sc.setKey(QKeySequence(cmd.key))
                sc.setContext(Qt.WidgetWithChildrenShortcut)
                sc.activated.connect(self.handle)
                self.id_to_cmd[sc.id()] = cmd

    def handle(self):
        cmd = self.id_to_cmd[self.sender().id()]
        if cmd.nargs and cmd.nargs != 0:
            self.set_cmd_text.emit(':{} '.format(cmd.name))
        else:
            cmd.run()

    def handle_empty(self):
        self.set_cmd_text.emit(':')
