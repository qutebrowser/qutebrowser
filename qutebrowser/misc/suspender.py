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
        self._cal_timer_period()
        self._set_timer()
        config.instance.changed.connect(self._toggle_timer)
        config.instance.changed.connect(self._set_timer_timemout)

    def _cal_timer_period(self):
        """Calculate the timer's period.

        Set the period to 1/5 of content.suspender.timeout.
        """
        self._tab_timeout = config.instance.get("content.suspender.timeout")
        secs = self._tab_timeout / 5
        self.timer_period = secs

    @config.change_filter('content.suspender.enabled')
    def _toggle_timer(self):
        self._set_timer()

    @config.change_filter('content.suspender.timeout')
    def _set_timer_timemout(self):
        self._cal_timer_period()
        self._set_timer()

    def _set_timer(self):
        if config.instance.get("content.suspender.enabled"):
            self.check_timer.start(self.timer_period * 1000)
        else:
            self.check_timer.stop()

    def _check_discard_tabs(self):
        """Iterate through all tabs and try to discard some tabs.

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
                        tab.background_time += self.timer_period
                        if tab.background_time > self._tab_timeout:
                            can_be_discarded.append(tab)
                        active_count += 1

        max_active_tabs = config.instance.get(
            "content.suspender.max_active_tabs")
        left = active_count - max_active_tabs
        while left > 0 and can_be_discarded:
            tab = can_be_discarded.pop()
            if self.should_discard(tab) and tab.discard():
                left -= 1
                tab.background_time = 0

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
