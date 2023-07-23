# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Zooming-related commands."""

from qutebrowser.api import cmdutils, apitypes, message, config


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def zoom_in(tab: apitypes.Tab, count: int = 1, quiet: bool = False) -> None:
    """Increase the zoom level for the current tab.

    Args:
        count: How many steps to zoom in.
        quiet: Don't show a zoom level message.
    """
    try:
        perc = tab.zoom.apply_offset(count)
    except ValueError as e:
        raise cmdutils.CommandError(e)
    if not quiet:
        message.info("Zoom level: {}%".format(int(perc)), replace='zoom-level')


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def zoom_out(tab: apitypes.Tab, count: int = 1, quiet: bool = False) -> None:
    """Decrease the zoom level for the current tab.

    Args:
        count: How many steps to zoom out.
        quiet: Don't show a zoom level message.
    """
    try:
        perc = tab.zoom.apply_offset(-count)
    except ValueError as e:
        raise cmdutils.CommandError(e)
    if not quiet:
        message.info("Zoom level: {}%".format(int(perc)), replace='zoom-level')


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def zoom(tab: apitypes.Tab,
         level: str = None,
         count: int = None,
         quiet: bool = False) -> None:
    """Set the zoom level for the current tab.

    The zoom can be given as argument or as [count]. If neither is
    given, the zoom is set to the default zoom. If both are given,
    use [count].

    Args:
        level: The zoom percentage to set.
        count: The zoom percentage to set.
        quiet: Don't show a zoom level message.
    """
    if count is not None:
        int_level = count
    elif level is not None:
        try:
            int_level = int(level.rstrip('%'))
        except ValueError:
            raise cmdutils.CommandError("zoom: Invalid int value {}"
                                        .format(level))
    else:
        int_level = int(config.val.zoom.default)

    try:
        tab.zoom.set_factor(int_level / 100)
    except ValueError:
        raise cmdutils.CommandError("Can't zoom {}%!".format(int_level))
    if not quiet:
        message.info("Zoom level: {}%".format(int_level), replace='zoom-level')
