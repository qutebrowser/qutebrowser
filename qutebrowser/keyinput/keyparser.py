# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Advanced keyparsers."""

import traceback

from PyQt5.QtCore import pyqtSlot

from qutebrowser.keyinput.basekeyparser import BaseKeyParser
from qutebrowser.utils import message, usertypes, utils
from qutebrowser.commands import runners, cmdexc
from qutebrowser.config import config

class KeyChainParser(BaseKeyParser):
    """KeyChainParser which implements chaining of multiple keys."""
    def __init__(self, win_id, parent=None, supports_count=False):
        super().__init__(win_id, parent, supports_count, supports_chains=True)
        self._partial_timer = usertypes.Timer(self, 'partial-match')
        self._partial_timer.setSingleShot(True)

    def __repr__(self):
        return utils.get_repr(self)

    def _handle_single_key(self, e):
        """Override _handle_single_key to abort if the key is a startchar.

        Args:
            e: the KeyPressEvent from Qt.

        Return:
            A self.Match member.
        """
        match = super()._handle_single_key(e)
        if match == self.Match.partial:
            timeout = config.val.input.partial_timeout
            if timeout != 0:
                self._partial_timer.setInterval(timeout)
                self._partial_timer.timeout.connect(self._clear_partial_match)
                self._partial_timer.start()
        return match

    @pyqtSlot()
    def _clear_partial_match(self):
        """Clear a partial keystring after a timeout."""
        self._debug_log("Clearing partial keystring {}".format(
            self._keystring))
        self._keystring = ''
        self.keystring_updated.emit(self._keystring)

    @pyqtSlot()
    def _stop_timers(self):
        super()._stop_timers()
        self._partial_timer.stop()
        try:
            self._partial_timer.timeout.disconnect(self._clear_partial_match)
        except TypeError:
            # no connections
            pass


class CommandKeyParser(KeyChainParser):

    """KeyChainParser for command bindings.

    Attributes:
        _commandrunner: CommandRunner instance.
    """

    def __init__(self, win_id, parent=None, supports_count=False):
        super().__init__(win_id, parent, supports_count)
        self._commandrunner = runners.CommandRunner(win_id)

    def execute(self, cmdstr, _keytype, count=None):
        try:
            self._commandrunner.run(cmdstr, count)
        except cmdexc.Error as e:
            message.error(str(e), stack=traceback.format_exc())

class PassthroughKeyParser(CommandKeyParser):

    """KeyChainParser which passes through normal keys.

    Used for insert/passthrough modes.

    Attributes:
        _mode: The mode this keyparser is for.
    """

    do_log = False
    passthrough = True

    def __init__(self, win_id, mode, parent=None):
        """Constructor.

        Args:
            mode: The mode this keyparser is for.
            parent: Qt parent.
        """
        super().__init__(win_id, parent, supports_count=False)
        self._read_config(mode)
        self._mode = mode

    def __repr__(self):
        return utils.get_repr(self, mode=self._mode)
