# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020 Coiby Xu <coiby.xu@gmail.com>
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

"""Management of tabs - suspend tab automatically."""

import typing

from qutebrowser.utils import objreg, log
from qutebrowser.config import config


suspender = typing.cast('Suspender', None)


class Suspender:

    def get_tab_page(self, tab):
        return tab._widget.page()

    def total_active_tabs(self):
        count = 0
        winlist = objreg.window_registry
        for win_id in sorted(winlist):
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            for tab in tabbed_browser.widgets():
                page = self.get_tab_page(tab)
                if page.lifecycleState() != page.LifecycleState.Discarded:
                    count += 1

        return count

    def should_discard(self, tab):
        return config.instance.get("content.suspender.max_active_tabs") > \
                   self.total_active_tabs() \
                and not tab.data.pinned \
                and not tab.data.fullscreen \
                and not tab.audio.is_recently_audible()

    def discard(self, tab):
        if self.should_discard(tab):
            page = self.get_tab_page(tab)
            page.setLifecycleState(page.LifecycleState.Discarded)
            tab.stop_suspender_timer()
            # change tabbar icon
            tab.indicator_color_restore = tab.get_indicator_color()
            tab.set_indicator_color(config.instance.get(
                                        "colors.suspender.discarded"))
            log.webview.debug("Tab #{} discard".format(repr(tab.tab_id)))

def init():
    """Initialize sessions.

    Args:
        parent: The parent to use for the SessionManager.
    """

    global suspender
    suspender = Suspender()
