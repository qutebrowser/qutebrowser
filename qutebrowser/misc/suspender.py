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

from PyQt5.QtCore import QTimer

from qutebrowser.utils import objreg, usertypes
from qutebrowser.config import config
from qutebrowser.misc import objects

suspender = typing.cast('Suspender', None)


class Suspender:

    """Automatically discard tabs.

    Ths suspender will check periodically all tabs and discard tabs
    meeting certain conditions.
    """

    def __init__(self):
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_discard_tabs)
        if config.instance.get("content.suspender.enabled"):
            self.check_timer.start(config.instance.get(
                "content.suspender.timeout") * 1000)

    def _check_discard_tabs(self):
        """Iterate through all tabs and try to discard some

        Only discard a tab if,
          - there are more than content.suspender.max_active_tabs tabs
          - it's not playing audio
          - it's not pinned

        """
        active_count = 0
        winlist = objreg.window_registry
        can_be_discarded = []
        for win_id in sorted(winlist):
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            current_tab = tabbed_browser.widget.currentWidget()
            active_count += 1
            for tab in tabbed_browser.widgets():
                if tab is not current_tab:
                    page = tab.get_page()
                    if page.lifecycleState() != page.LifecycleState.Discarded:
                        if tab.discard_next_cycle:
                            can_be_discarded.append(tab)
                        else:
                            tab.discard_next_cycle = True
                        active_count += 1

        max_active_tabs = config.instance.get(
            "content.suspender.max_active_tabs")
        left = active_count - max_active_tabs
        while left > 0 and can_be_discarded:
            tab = can_be_discarded.pop()
            if self.should_discard(tab) and tab.discard():
                left -= 1
                self.discard_next_cycle = False

    def in_whitelist(self, tab):
        """check if a tab is whitelisted."""
        url = tab.url()
        for pattern in config.instance.get("content.suspender.whitelist"):
            if pattern.matches(url):
                return True
        return False

    def should_discard(self, tab):
        return (not tab.data.pinned and not
                tab.data.fullscreen and not
                tab.audio.is_recently_audible() and not
                self.in_whitelist(tab))


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
