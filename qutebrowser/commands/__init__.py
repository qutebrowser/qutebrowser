# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""In qutebrowser, all keybindings are mapped to commands.

Some commands are hidden, which means they don't show up in the command
completion when pressing `:`, as they're typically not useful to run by hand.

For command arguments, there are also some variables you can use:

- `{url}` expands to the URL of the current page
- `{url:pretty}` expands to the URL in decoded format
- `{clipboard}` expands to the clipboard contents
- `{primary}` expands to the primary selection contents

It is possible to run or bind multiple commands by separating them with `;;`.
"""
