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

"""In qutebrowser, all keybindings are mapped to commands.

Some commands are hidden, which means they don't show up in the command
completion when pressing `:`, as they're typically not useful to run by hand.

For command arguments, there are also some variables you can use:

- `{url}` expands to the URL of the current page
- `{url:pretty}` expands to the URL in decoded format
- `{url:host}`, `{url:domain}`, `{url:auth}`, `{url:scheme}`, `{url:username}`,
  `{url:password}`, `{url:host}`, `{url:port}`, `{url:path}` and `{url:query}`
  expand to the respective parts of the current URL
- `{title}` expands to the current page's title
- `{clipboard}` expands to the clipboard contents
- `{primary}` expands to the primary selection contents

Those variables can be escaped by doubling the braces, e.g. `{{url}}`. It is
possible to run or bind multiple commands by separating them with `;;`.
"""
