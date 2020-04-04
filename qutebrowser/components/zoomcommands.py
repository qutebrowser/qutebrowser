# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Zooming-related commands."""

from qutebrowser.api import cmdutils, apitypes, message, config
from qutebrowser.browser import pdfjs


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def zoom_in(tab: apitypes.Tab, no_pdfjs: bool = False, count: int = 1,
            quiet: bool = False) -> None:
    """Increase the zoom level for the current tab.

    Args:
        no_pdfjs: Use browser's zoom even if the tab displays PDF.js.
        count: How many steps to zoom in.
        quiet: Don't show a zoom level message.
    """
    if pdfjs.is_pdfjs_page(tab) and not no_pdfjs:
        pdfjs.zoom_in(tab, count)
        return
    try:
        perc = tab.zoom.apply_offset(count)
    except ValueError as e:
        raise cmdutils.CommandError(e)
    if not quiet:
        message.info("Zoom level: {}%".format(int(perc)), replace=True)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def zoom_out(tab: apitypes.Tab, no_pdfjs: bool = False, count: int = 1,
             quiet: bool = False) -> None:
    """Decrease the zoom level for the current tab.

    Args:
        no_pdfjs: Use browser's zoom even if the tab displays PDF.js.
        count: How many steps to zoom out.
        quiet: Don't show a zoom level message.
    """
    if pdfjs.is_pdfjs_page(tab) and not no_pdfjs:
        pdfjs.zoom_out(tab, count)
        return
    try:
        perc = tab.zoom.apply_offset(-count)
    except ValueError as e:
        raise cmdutils.CommandError(e)
    if not quiet:
        message.info("Zoom level: {}%".format(int(perc)), replace=True)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def zoom(tab: apitypes.Tab,
         no_pdfjs: bool = False,
         level: str = None,
         count: int = None,
         quiet: bool = False) -> None:
    """Set the zoom level for the current tab.

    The zoom can be given as argument or as [count]. If neither is
    given, the zoom is set to the default zoom. If both are given,
    use [count].

    Args:
        no_pdfjs: Use browser's zoom even if the tab displays PDF.js.
        level: The zoom percentage to set.
        count: The zoom percentage to set.
        quiet: Don't show a zoom level message.
    """
    use_default_zoom = False
    if count is not None:
        int_level = count
    elif level is not None:
        try:
            int_level = int(level.rstrip('%'))
        except ValueError:
            raise cmdutils.CommandError("zoom: Invalid int value {}"
                                        .format(level))
    else:
        use_default_zoom = True

    if pdfjs.is_pdfjs_page(tab) and not no_pdfjs:
        if use_default_zoom:
            pdfjs.zoom(tab)
        else:
            pdfjs.zoom(tab, int_level / 100)
        return

    if use_default_zoom:
        int_level = int(config.val.zoom.default)

    try:
        tab.zoom.set_factor(int_level / 100)
    except ValueError:
        raise cmdutils.CommandError("Can't zoom {}%!".format(int_level))
    if not quiet:
        message.info("Zoom level: {}%".format(int_level), replace=True)
