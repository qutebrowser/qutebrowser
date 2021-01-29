# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Commands relating to ad blocking."""

from qutebrowser.api import cmdutils
from qutebrowser.components import braveadblock, hostblock


@cmdutils.register()
def adblock_update() -> None:
    """Update block lists for both the host- and the Brave ad blocker."""
    if braveadblock.ad_blocker is not None:
        braveadblock.ad_blocker.adblock_update()
    hostblock.host_blocker.adblock_update()
