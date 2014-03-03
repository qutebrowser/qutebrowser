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

"""All command classes.

These are automatically propagated from commands.utils
via inspect.

A command class can set the following properties:

    nargs -- Number of arguments. Either a number, '?' (0 or 1), '+' (1 or
             more), or '*' (any). Default: 0
    name -- The name of the command, or a list of aliases.
    split_args -- If arguments should be split or not. Default: True
    count -- If the command supports a count. Default: False
    hide -- If the command should be hidden in tab completion. Default: False

"""
