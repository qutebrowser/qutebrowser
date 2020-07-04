from qutebrowser.api import cmdutils
from qutebrowser.components import braveadblock, adblock


@cmdutils.register()
def adblock_update() -> None:
    """Update the adblock block lists for both the host blocker and the brave adblocker."""

    if braveadblock.ad_blocker is not None:
        braveadblock.ad_blocker.adblock_update()
    adblock.host_blocker.adblock_update()
