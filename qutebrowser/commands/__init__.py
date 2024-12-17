# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""In qutebrowser, all keybindings are mapped to commands.

Some commands are hidden, which means they don't show up in the command
completion when pressing `:`, as they're typically not useful to run by hand.

For command arguments, there are also some variables you can use:

- `{url}` expands to the URL of the current page
- `{url:pretty}` expands to the URL in decoded format
- `{url:host}`, `{url:domain}`, `{url:auth}`, `{url:scheme}`, `{url:username}`,
  `{url:password}`, `{url:port}`, `{url:path}` and `{url:query}`
  expand to the respective parts of the current URL
- `{url:yank}` expands to the URL of the current page but strips all the query
  parameters in the `url.yank_ignored_parameters` setting.
- `{title}` expands to the current page's title
- `{clipboard}` expands to the clipboard contents
- `{primary}` expands to the primary selection contents

Those variables can be escaped by doubling the braces, e.g. `{{url}}`. It is
possible to run or bind multiple commands by separating them with `;;`.
"""
