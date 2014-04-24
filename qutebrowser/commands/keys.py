# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Parse keypresses/keychains in the main window.

Module attributes:
    STARTCHARS: Possible chars for starting a commandline input.
"""

import logging

from PyQt5.QtCore import pyqtSignal

from qutebrowser.utils.keyparser import KeyChainParser
from qutebrowser.commands.parsers import (CommandParser, ArgumentCountError,
                                          NoSuchCommandError)

STARTCHARS = ":/?"


class CommandKeyParser(KeyChainParser):

    """KeyChainParser for command bindings.

    Class attributes:
        supports_count: If the keyparser should support counts.

    Attributes:
        commandparser: Commandparser instance.

    Signals:
        set_cmd_text: Emitted when the statusbar should set a partial command.
                      arg: Text to set.
    """

    set_cmd_text = pyqtSignal(str)
    supports_count = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self.commandparser = CommandParser()
        self.read_config('keybind')

    def _run_or_fill(self, cmdstr, count=None, ignore_exc=True):
        """Run the command in cmdstr or fill the statusbar if args missing.

        Args:
            cmdstr: The command string.
            count: Optional command count.
            ignore_exc: Ignore exceptions.

        Emit:
            set_cmd_text: If a partial command should be printed to the
                          statusbar.
        """
        try:
            self.commandparser.run(cmdstr, count=count, ignore_exc=ignore_exc)
        except NoSuchCommandError:
            pass
        except ArgumentCountError:
            logging.debug('Filling statusbar with partial command {}'.format(
                cmdstr))
            self.set_cmd_text.emit(':{} '.format(cmdstr))

    def _handle_single_key(self, e):
        """Override _handle_single_key to abort if the key is a startchar.

        Args:
            e: the KeyPressEvent from Qt.

        Emit:
            set_cmd_text: If the keystring should be shown in the statusbar.

        Return:
            True if event has been handled, False otherwise.
        """
        txt = e.text().strip()
        if not self._keystring and any(txt == c for c in STARTCHARS):
            self.set_cmd_text.emit(txt)
            return True
        return super()._handle_single_key(e)

    def execute(self, cmdstr, count=None):
        """Handle a completed keychain."""
        self._run_or_fill(cmdstr, count, ignore_exc=False)
