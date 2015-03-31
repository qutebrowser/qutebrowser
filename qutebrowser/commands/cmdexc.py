# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Exception classes for commands modules.

Defined here to avoid circular dependency hell.
"""


class CommandError(Exception):

    """Raised when a command encounters a error while running."""

    pass


class CommandMetaError(Exception):

    """Common base class for exceptions occurring before a command is run."""


class NoSuchCommandError(CommandMetaError):

    """Raised when a command wasn't found."""

    pass


class ArgumentCountError(CommandMetaError):

    """Raised when a command was called with an invalid count of arguments."""

    pass


class ArgumentTypeError(CommandMetaError):

    """Raised when an argument had an invalid type."""

    pass


class PrerequisitesError(CommandMetaError):

    """Raised when a cmd can't be used because some prerequisites aren't met.

    This is raised for example when we're in the wrong mode while executing the
    command, or we need javascript enabled but don't have done so.
    """

    pass
