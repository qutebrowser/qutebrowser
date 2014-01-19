from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence
import logging

class KeyParser(QObject):
    keystring = ''
    set_cmd_text = pyqtSignal(str)
    key_to_cmd = {}

    def from_cmd_dict(self, d):
        for cmd in d.values():
            if cmd.key is not None:
                logging.debug('registered: {} -> {}'.format(cmd.name, cmd.key))
                self.key_to_cmd[cmd.key] = cmd

    def handle(self, e):
        logging.debug('Got key: {} / text: {}'.format(e.key(), e.text()))
        self.keystring += e.text()
        if self.keystring == ':':
            self.set_cmd_text.emit(':')
            self.keystring = ''
            return
        try:
            cmd = self.key_to_cmd[self.keystring]
        except KeyError:
            logging.debug('No match for "{}" (added {})'.format(self.keystring, e.text()))
            pass
        else:
            self.keystring = ''
            if cmd.nargs and cmd.nargs != 0:
                self.set_cmd_text.emit(':{} '.format(cmd.name))
            else:
                cmd.run()
