from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence
import logging
import re

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
        logging.debug('Got key: {} / text: "{}"'.format(e.key(), e.text()))
        txt = e.text().strip()
        if not txt:
            logging.debug('Ignoring, no text')
            return

        self.keystring += txt

        if self.keystring == ':':
            self.set_cmd_text.emit(':')
            self.keystring = ''
            return

        (countstr, cmdstr) = re.match('^(\d*)(.*)', self.keystring).groups()

        if not cmdstr:
            return

        try:
            cmd = self.key_to_cmd[cmdstr]
        except KeyError:
            pos = len(cmdstr)
            if any([cmdstr[-1] == needle[pos-1]
                    for needle in self.key_to_cmd]):
                logging.debug('No match for "{}" (added {})'.format(
                    self.keystring, txt))
            else:
                logging.debug('Giving up with "{}", no matches'.format(
                    self.keystring))
                self.keystring = ''
                return

        self.keystring = ''
        count = int(countstr) if countstr else None

        if cmd.nargs and cmd.nargs != 0:
            logging.debug('Filling statusbar with partial command {}'.format(
                cmd.name))
            self.set_cmd_text.emit(':{} '.format(cmd.name))
        else:
            if count is not None:
                cmd.run(count=count)
            else:
                cmd.run()
