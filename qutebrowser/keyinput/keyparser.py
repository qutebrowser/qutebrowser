# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

from qutebrowser.keyinput.basekeyparser import BaseKeyParser
from qutebrowser.utils import message
from qutebrowser.commands import runners, cmdexc


class CommandKeyParser(BaseKeyParser):

    """KeyChainParser for command bindings.

    Attributes:
        commandrunner: CommandRunner instance.
    """

    def __init__(self, parent=None, supports_count=None,
                 supports_chains=False):
        super().__init__(parent, supports_count, supports_chains)
        self.commandrunner = runners.CommandRunner()

    def execute(self, cmdstr, _keytype, count=None):
        try:
            self.commandrunner.run(cmdstr, count)
        except (cmdexc.CommandMetaError, cmdexc.CommandError) as e:
            message.error(e, immediately=True)


class PassthroughKeyParser(CommandKeyParser):

    """KeyChainParser which passes through normal keys.

    Used for insert/passthrough modes.

    Attributes:
        _mode: The mode this keyparser is for.
    """

    do_log = False

    def __init__(self, mode, parent=None, warn=True):
        """Constructor.

        Args:
            mode: The mode this keyparser is for.
            parent: Qt parent.
            warn: Whether to warn if an ignored key was bound.
        """
        super().__init__(parent, supports_chains=False)
        self.log = False
        self.warn_on_keychains = warn
        self.read_config(mode)
        self._mode = mode

    def __repr__(self):
        return '<{} mode={}, warn={})'.format(
            self.__class__.__name__, self._mode, self.warn_on_keychains)
