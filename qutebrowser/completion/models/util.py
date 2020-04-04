# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Utility functions for completion models."""

import typing

from qutebrowser.utils import usertypes
from qutebrowser.misc import objects


DeleteFuncType = typing.Callable[[typing.Sequence[str]], None]


def get_cmd_completions(info, include_hidden, include_aliases, prefix=''):
    """Get a list of completions info for commands, sorted by name.

    Args:
        info: The CompletionInfo.
        include_hidden: Include commands which are not in normal mode.
        include_aliases: True to include command aliases.
        prefix: String to append to the command name.

    Return: A list of tuples of form (name, description, bindings).
    """
    assert objects.commands
    cmdlist = []
    cmd_to_keys = info.keyconf.get_reverse_bindings_for('normal')
    for obj in set(objects.commands.values()):
        hide_debug = obj.debug and not objects.args.debug
        hide_mode = (usertypes.KeyMode.normal not in obj.modes and
                     not include_hidden)
        if not (hide_debug or hide_mode or obj.deprecated):
            bindings = ', '.join(cmd_to_keys.get(obj.name, []))
            cmdlist.append((prefix + obj.name, obj.desc, bindings))

    if include_aliases:
        for name, cmd in info.config.get('aliases').items():
            bindings = ', '.join(cmd_to_keys.get(name, []))
            cmdlist.append((name, "Alias for '{}'".format(cmd), bindings))

    return sorted(cmdlist)
