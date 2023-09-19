# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Commands relating to ad blocking."""

from qutebrowser.api import cmdutils
from qutebrowser.components import braveadblock, hostblock


@cmdutils.register()
def adblock_update() -> None:
    """Update block lists for both the host- and the Brave ad blocker."""
    if braveadblock.ad_blocker is not None:
        braveadblock.ad_blocker.adblock_update()
    hostblock.host_blocker.adblock_update()
