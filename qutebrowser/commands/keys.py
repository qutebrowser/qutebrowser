import logging
import re

from PyQt5.QtCore import QObject, pyqtSignal

import qutebrowser.commands.utils as cmdutils

class KeyParser(QObject):
    """Parser for vim-like key sequences"""
    keystring = '' # The currently entered key sequence
    # Signal emitted when the statusbar should set a partial command
    set_cmd_text = pyqtSignal(str)
    # Signal emitted when the keystring is updated
    keystring_updated = pyqtSignal(str)
    # Keybindings
    key_to_cmd = {}

    MATCH_PARTIAL = 0
    MATCH_DEFINITIVE = 1
    MATCH_NONE = 2

    def from_config_sect(self, sect):
        """Loads keybindings from a ConfigParser section, in the config format
        key = command, e.g.
        gg = scrollstart
        """
        for (key, cmd) in sect.items():
            logging.debug('registered key: {} -> {}'.format(key, cmd))
            self.key_to_cmd[key] = cmdutils.cmd_dict[cmd]

    def handle(self, e):
        """Wrapper for _handle to emit keystring_updated after _handle"""
        self._handle(e)
        self.keystring_updated.emit(self.keystring)

    def _handle(self, e):
        """Handle a new keypress.

        e -- the KeyPressEvent from Qt
        """
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

        # FIXME this doesn't handle ambigious keys correctly.
        #
        # If a keychain is ambigious, we probably should set up a QTimer with a
        # configurable timeout, which triggers cmd.run() when expiring. Then
        # when we enter _handle() again in time we stop the timer.

        (match, cmd) = self._match_key(cmdstr)

        if match == self.MATCH_DEFINITIVE:
            pass
        elif match == self.MATCH_PARTIAL:
            logging.debug('No match for "{}" (added {})'.format(self.keystring,
                                                                txt))
            return
        elif match == self.MATCH_NONE:
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
        elif count is not None:
            cmd.run(count=count)
        else:
            cmd.run()

    def _match_key(self, cmdstr):
        """Tries to match a given cmdstr with any defined command"""
        try:
            cmd = self.key_to_cmd[cmdstr]
            return (self.MATCH_DEFINITIVE, cmd)
        except KeyError:
            # No definitive match, check if there's a chance of a partial match
            for cmd in self.key_to_cmd:
                try:
                    if cmdstr[-1] == cmd[len(cmdstr) - 1]:
                        return (self.MATCH_PARTIAL, None)
                except IndexError:
                    # current cmd is shorter than our cmdstr, so it won't match
                    continue
            # no definitive and no partial matches if we arrived here
            return (self.MATCH_NONE, None)
