# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Access to the qutebrowser configuration."""

from typing import cast, Any

from qutebrowser.qt.core import QUrl

from qutebrowser.config import config

#: Simplified access to config values using attribute access.
#: For example, to access the ``content.javascript.enabled`` setting,
#: you can do::
#:
#:   if config.val.content.javascript.enabled:
#:       ...
#:
#: This also supports setting configuration values::
#:
#:   config.val.content.javascript.enabled = False
val = cast('config.ConfigContainer', None)


def get(name: str, url: QUrl = None) -> Any:
    """Get a value from the config based on a string name."""
    return config.instance.get(name, url)
