# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exception classes for commands modules.

Defined here to avoid circular dependency hell.
"""

from typing import List
import difflib


class Error(Exception):

    """Base class for all cmdexc errors."""


class NoSuchCommandError(Error):

    """Raised when a command isn't found."""

    @classmethod
    def for_cmd(cls, cmd: str, all_commands: List[str] = None) -> "NoSuchCommandError":
        """Raise an exception for the given command."""
        suffix = ''
        if all_commands:
            matches = difflib.get_close_matches(cmd, all_commands, n=1)
            if matches:
                suffix = f' (did you mean :{matches[0]}?)'
        return cls(f"{cmd}: no such command{suffix}")


class EmptyCommandError(NoSuchCommandError):

    """Raised when no command was given."""

    def __init__(self):
        super().__init__("No command given")


class ArgumentTypeError(Error):

    """Raised when an argument is an invalid type."""


class PrerequisitesError(Error):

    """Raised when a cmd can't be used because some prerequisites aren't met.

    This is raised for example when we're in the wrong mode while executing the
    command, or we need javascript enabled but haven't done so.
    """
