# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from functools import partial

from PyQt5.QtCore import QObject

from qutebrowser.utils.debug import dbg_signal, signal_name
from qutebrowser.widgets.webview import WebView
from qutebrowser.utils.log import signals as logger


class SignalFilter(QObject):

    """A filter for signals.

    Signals are only passed to the parent TabbedBrowser if they originated in
    the currently shown widget.

    Attributes:
        _tabs: The QTabWidget associated with this SignalFilter.

    Class attributes:
        BLACKLIST: List of signal names which should not be logged.
    """

    BLACKLIST = ['cur_scroll_perc_changed', 'cur_progress']

    def __init__(self, tabs):
        super().__init__(tabs)
        self._tabs = tabs

    def create(self, signal, tab):
        """Factory for partial _filter_signals functions.

        Args:
            signal: The pyqtSignal to filter.
            tab: The WebView to create filters for.

        Return:
            A partial functon calling _filter_signals with a signal.
        """
        if not isinstance(tab, WebView):
            raise ValueError("Tried to create filter for {} which is no "
                             "WebView!".format(tab))
        return partial(self._filter_signals, signal, tab)

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

        Emit:
            The target signal if the sender was the current widget.
        """
        log_signal = signal_name(signal) not in self.BLACKLIST
        try:
            tabidx = self._tabs.indexOf(tab)
        except RuntimeError:
            # The tab has been deleted already
            return
        if tabidx == self._tabs.currentIndex():
            if log_signal:
                logger.debug("emitting: {} (tab {})".format(
                    dbg_signal(signal, args), tabidx))
            signal.emit(*args)
        else:
            if log_signal:
                logger.debug("ignoring: {} (tab {})".format(
                    dbg_signal(signal, args), tabidx))
