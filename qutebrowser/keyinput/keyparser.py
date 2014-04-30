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

"""Advanced keyparsers."""

import logging

from qutebrowser.keyinput._basekeyparser import BaseKeyParser
import qutebrowser.utils.message as message

from qutebrowser.commands.managers import CommandManager
from qutebrowser.commands._exceptions import ArgumentCountError, CommandError


class CommandKeyParser(BaseKeyParser):

    """KeyChainParser for command bindings.

    Attributes:
        commandmanager: CommandManager instance.
    """

    def __init__(self, parent=None, supports_count=None,
                 supports_chains=False):
        super().__init__(parent, supports_count, supports_chains)
        self.commandmanager = CommandManager()

    def _run_or_fill(self, cmdstr, count=None):
        """Run the command in cmdstr or fill the statusbar if args missing.

        Args:
            cmdstr: The command string.
            count: Optional command count.
        """
        try:
            self.commandmanager.run(cmdstr, count=count)
        except ArgumentCountError:
            logging.debug("Filling statusbar with partial command {}".format(
                cmdstr))
            message.set_cmd_text(':{} '.format(cmdstr))
        except CommandError as e:
            message.error(str(e))

    def execute(self, cmdstr, _keytype, count=None):
        self._run_or_fill(cmdstr, count)


class PassthroughKeyParser(CommandKeyParser):

    """KeyChainParser which passes through normal keys.

    Used for insert/passthrough modes.
    """

    def __init__(self, confsect, parent=None):
        """Constructor.

        Args:
            confsect: The config section to use.
        """
        super().__init__(parent, supports_chains=False)
        self.read_config(confsect)
