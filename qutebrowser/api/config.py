# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Access to the qutebrowser configuration."""

from typing import cast, Any

from PyQt5.QtCore import QUrl

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
