# SPDX-FileCopyrightText: Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utility functions for completion models."""

from collections.abc import Sequence, Callable

from qutebrowser.utils import usertypes
from qutebrowser.misc import objects


DeleteFuncType = Callable[[Sequence[str]], None]


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
        hide_ni = obj.name == 'Ni!'
        if not (hide_debug or hide_mode or obj.deprecated or hide_ni):
            bindings = ', '.join(cmd_to_keys.get(obj.name, []))
            cmdlist.append((prefix + obj.name, obj.desc, bindings))

    if include_aliases:
        for name, cmd in info.config.get('aliases').items():
            bindings = ', '.join(cmd_to_keys.get(name, []))
            cmdlist.append((name, "Alias for '{}'".format(cmd), bindings))

    return sorted(cmdlist)
