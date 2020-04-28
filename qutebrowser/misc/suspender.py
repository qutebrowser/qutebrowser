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

from qutebrowser.utils import objreg, log, usertypes
from qutebrowser.config import config
from qutebrowser.misc import objects

suspender = typing.cast('Suspender', None)


class Suspender:

    """Automatically discard tabs."""

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

    def in_whitelist(self, tab):
        url = tab.url()
        for pattern in config.instance.get("content.suspender.whitelist"):
            if pattern.matches(url):
                return True
        return False

    def should_discard(self, tab):
        return (config.instance.get("content.suspender.max_active_tabs") <
                self.total_active_tabs() and not
                tab.data.pinned and not
                tab.data.fullscreen and not
                tab.audio.is_recently_audible() and not
                self.in_whitelist(tab))

    def start_timer(self, tab):
        if config.instance.get("content.suspender.enabled"):
            tab.start_suspender_timer()

    def stop_timer(self, tab):
        if config.instance.get("content.suspender.enabled"):
            tab.stop_suspender_timer()

    def discard(self, tab):
        if self.should_discard(tab):
            page = self.get_tab_page(tab)
            page.setLifecycleState(page.LifecycleState.Discarded)
            return page.lifecycleState() == page.LifecycleState.Discarded

        return False


def init():
    """Initialize suspender.

    Suspender use the QWebEnginePage.LifecycleState API which is only
    supported by QtWebEngine >= 5.14.

    """
    if objects.backend == usertypes.Backend.QtWebEngine:
        from PyQt5.QtWebEngineWidgets import QWebEnginePage
        if hasattr(QWebEnginePage, 'LifecycleState'):
            global suspender
            suspender = Suspender()
