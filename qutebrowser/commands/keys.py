"""Parse keypresses/keychains in the main window."""


import logging
import re

from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QKeySequence

from qutebrowser.commands.utils import (CommandParser, ArgumentCountError,
                                        NoSuchCommandError)

# Possible chars for starting a commandline input
startchars = ":/?"


class KeyParser(QObject):
    """Parser for vim-like key sequences."""
    keystring = ''  # The currently entered key sequence
    # Signal emitted when the statusbar should set a partial command
    set_cmd_text = pyqtSignal(str)
    # Signal emitted when the keystring is updated
    keystring_updated = pyqtSignal(str)
    # Keybindings
    bindings = {}
    modifier_bindings = {}
    commandparser = None

    MATCH_PARTIAL = 0
    MATCH_DEFINITIVE = 1
    MATCH_NONE = 2

    def __init__(self, mainwindow):
        super().__init__(mainwindow)
        self.commandparser = CommandParser()

    def from_config_sect(self, sect):
        """Load keybindings from a ConfigParser section.

        Config format: key = command, e.g.:
        gg = scrollstart
        """
        for (key, cmd) in sect.items():
            if key.startswith('@') and key.endswith('@'):
                # normalize keystring
                keystr = self._normalize_keystr(key.strip('@'))
                logging.debug('registered mod key: {} -> {}'.format(keystr,
                                                                    cmd))
                self.modifier_bindings[keystr] = cmd
            else:
                logging.debug('registered key: {} -> {}'.format(key, cmd))
                self.bindings[key] = cmd

    def handle(self, e):
        """Handle a new keypress and call the respective handlers.

        e -- the KeyPressEvent from Qt
        """
        handled = self._handle_modifier_key(e)
        if not handled:
            self._handle_single_key(e)
            self.keystring_updated.emit(self.keystring)

    def _handle_modifier_key(self, e):
        """Handle a new keypress with modifiers.

        Returns True if the keypress has been handled, and False if not.

        e -- the KeyPressEvent from Qt
        """
        MODMASK2STR = {
            Qt.ControlModifier: 'Ctrl',
            Qt.AltModifier: 'Alt',
            Qt.MetaModifier: 'Meta',
            Qt.ShiftModifier: 'Shift'
        }
        if e.key() in [Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta]:
            # Only modifier pressed
            return False
        mod = e.modifiers()
        modstr = ''
        if not mod & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
            # won't be a shortcut with modifiers
            return False
        for (mask, s) in MODMASK2STR.items():
            if mod & mask:
                modstr += s + '+'
        keystr = QKeySequence(e.key()).toString()
        try:
            cmdstr = self.modifier_bindings[modstr + keystr]
        except KeyError:
            logging.debug('No binding found for {}.'.format(modstr + keystr))
            return True
        self._run_or_fill(cmdstr, ignore_exc=False)
        return True

    def _handle_single_key(self, e):
        """Handle a new keypress with a single key (no modifiers).

        Separates the keypress into count/command, then checks if it matches
        any possible command, and either runs the command, ignores it, or
        displays an error.

        e -- the KeyPressEvent from Qt
        """
        logging.debug('Got key: {} / text: "{}"'.format(e.key(), e.text()))
        txt = e.text().strip()
        if not txt:
            logging.debug('Ignoring, no text')
            return

        self.keystring += txt

        if any(self.keystring == c for c in startchars):
            self.set_cmd_text.emit(self.keystring)
            self.keystring = ''
            return

        (countstr, cmdstr_needle) = re.match(r'^(\d*)(.*)',
                                             self.keystring).groups()

        if not cmdstr_needle:
            return

        # FIXME this doesn't handle ambigious keys correctly.
        #
        # If a keychain is ambigious, we probably should set up a QTimer with a
        # configurable timeout, which triggers cmd.run() when expiring. Then
        # when we enter _handle() again in time we stop the timer.

        (match, cmdstr_hay) = self._match_key(cmdstr_needle)

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
        self._run_or_fill(cmdstr_hay, count=count, ignore_exc=False)
        return

    def _match_key(self, cmdstr_needle):
        """Try to match a given keystring with any bound keychain.

        cmdstr_needle: The command string to find.
        """
        try:
            cmdstr_hay = self.bindings[cmdstr_needle]
            return (self.MATCH_DEFINITIVE, cmdstr_hay)
        except KeyError:
            # No definitive match, check if there's a chance of a partial match
            for hay in self.bindings:
                try:
                    if cmdstr_needle[-1] == hay[len(cmdstr_needle) - 1]:
                        return (self.MATCH_PARTIAL, None)
                except IndexError:
                    # current cmd is shorter than our cmdstr_needle, so it
                    # won't match
                    continue
            # no definitive and no partial matches if we arrived here
            return (self.MATCH_NONE, None)

    def _normalize_keystr(self, keystr):
        """Normalizes a keystring like Ctrl-Q to a keystring like Ctrl+Q.

        keystr -- The key combination as a string.
        """
        replacements = [
            ('Control', 'Ctrl'),
            ('Windows', 'Meta'),
            ('Mod1', 'Alt'),
            ('Mod4', 'Meta'),
        ]
        for (orig, repl) in replacements:
            keystr = keystr.replace(orig, repl)
        for mod in ['Ctrl', 'Meta', 'Alt', 'Shift']:
            keystr = keystr.replace(mod + '-', mod + '+')
        keystr = QKeySequence(keystr).toString()
        return keystr

    def _run_or_fill(self, cmdstr, count=None, ignore_exc=True):
        """Runs the command in cmdstr or fills the statusbar if args missing.

        cmdstr -- The command string.
        count -- Optional command count.
        ignore_exc -- Ignore exceptions.
        """
        try:
            self.commandparser.run(cmdstr, count=count, ignore_exc=ignore_exc)
        except NoSuchCommandError:
            pass
        except ArgumentCountError:
            logging.debug('Filling statusbar with partial command {}'.format(
                cmdstr))
            self.set_cmd_text.emit(':{} '.format(cmdstr))
        return
