# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

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
