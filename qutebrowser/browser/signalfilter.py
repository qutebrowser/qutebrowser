# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""A filter for signals which either filters or passes them."""

import functools

from PyQt5.QtCore import QObject

from qutebrowser.utils import debug, log, objreg


class SignalFilter(QObject):

    """A filter for signals.

    Signals are only passed to the parent TabbedBrowser if they originated in
    the currently shown widget.

    Attributes:
        _win_id: The window ID this SignalFilter is associated with.

    Class attributes:
        BLACKLIST: List of signal names which should not be logged.
    """

    BLACKLIST = ['cur_scroll_perc_changed', 'cur_progress',
                 'cur_statusbar_message', 'cur_link_hovered']

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id

    def create(self, signal, tab):
        """Factory for partial _filter_signals functions.

        Args:
            signal: The pyqtSignal to filter.
            tab: The WebView to create filters for.

        Return:
            A partial functon calling _filter_signals with a signal.
        """
        return functools.partial(self._filter_signals, signal, tab)

    def _filter_signals(self, signal, tab, *args):
        """Filter signals and trigger TabbedBrowser signals if needed.

        Triggers signal if the original signal was sent from the _current_ tab
        and not from any other one.

        The original signal does not matter, since we get the new signal and
        all args.

        Args:
            signal: The signal to emit if the sender was the current widget.
            tab: The WebView which the filter belongs to.
            *args: The args to pass to the signal.
        """
        log_signal = debug.signal_name(signal) not in self.BLACKLIST
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        try:
            tabidx = tabbed_browser.indexOf(tab)
        except RuntimeError:
            # The tab has been deleted already
            return
        if tabidx == tabbed_browser.currentIndex():
            if log_signal:
                log.signals.debug("emitting: {} (tab {})".format(
                    debug.dbg_signal(signal, args), tabidx))
            signal.emit(*args)
        else:
            if log_signal:
                log.signals.debug("ignoring: {} (tab {})".format(
                    debug.dbg_signal(signal, args), tabidx))
