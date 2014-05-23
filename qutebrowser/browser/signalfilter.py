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

from qutebrowser.utils.signals import dbg_signal
from qutebrowser.widgets.webview import WebView
from qutebrowser.utils.log import signals as logger


class SignalFilter(QObject):

    """A filter for signals.

    Signals are only passed to the parent TabbedBrowser if they originated in
    the currently shown widget.

    Attributes:
        _tabs: The QTabWidget associated with this SignalFilter.
    """

    def __init__(self, tabs):
        super().__init__(tabs)
        self._tabs = tabs

    def create(self, signal):
        """Factory for partial _filter_signals functions.

        Args:
            signal: The pyqtSignal to filter.

        Return:
            A partial functon calling _filter_signals with a signal.
        """
        return partial(self._filter_signals, signal)

    def _filter_signals(self, signal, *args):
        """Filter signals and trigger TabbedBrowser signals if needed.

        Triggers signal if the original signal was sent from the _current_ tab
        and not from any other one.

        The original signal does not matter, since we get the new signal and
        all args.

        Args:
            signal: The signal to emit if the sender was the current widget.
            *args: The args to pass to the signal.

        Emit:
            The target signal if the sender was the current widget.
        """
        sender = self.sender()
        log_signal = not signal.signal.startswith('2cur_progress')
        if not isinstance(sender, WebView):
            # BUG? This should never happen, but it does regularely...
            logger.warn("Got signal {} by {} which is no tab!".format(
                dbg_signal(signal, args), sender))
            return
        if self._tabs.currentWidget() == sender:
            if log_signal:
                logger.debug("emitting: {} (tab {})".format(
                    dbg_signal(signal, args), self._tabs.indexOf(sender)))
            signal.emit(*args)
        else:
            if log_signal:
                logger.debug("ignoring: {} (tab {})".format(
                    dbg_signal(signal, args), self._tabs.indexOf(sender)))
