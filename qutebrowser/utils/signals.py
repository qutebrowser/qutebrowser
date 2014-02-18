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

"""Utilities regarding signals."""

import re
import logging
from collections import OrderedDict

from PyQt5.QtCore import QObject


def signal_name(sig):
    """Return a cleaned up name of a signal."""
    m = re.match(r'[0-9]+(.*)\(.*\)', sig.signal)
    return m.group(1)


def dbg_signal(sig, args):
    """Return a string representation of a signal for debugging.

    sig -- A pyqtSignal.
    args -- The arguments as list of strings.

    """
    return '{}({})'.format(signal_name(sig), ', '.join(map(str, args)))


class SignalCache(QObject):

    """Cache signals emitted by an object, and re-emit them later.

    Attributes:
        _uncached: A list of signals which should not be cached.
        _signal_dict: The internal mapping of signals we got.

    """

    def __init__(self, uncached=None):
        """Create a new SignalCache.

        uncached -- A list of signal names (as string) which should never be
                    cached.

        """
        super().__init__()
        if uncached is None:
            self._uncached = []
        else:
            self._uncached = uncached
        self._signal_dict = OrderedDict()

    def add(self, sig, args):
        """Add a new signal to the signal cache.

        If the signal doesn't need caching it will be ignored.
        If it's already in the cache, it'll be updated and moved to the front.
        If not, it will be added.

        """
        if not self._signal_needs_caching(sig):
            return
        had_signal = sig.signal in self._signal_dict
        self._signal_dict[sig.signal] = (sig, args)
        if had_signal:
            self._signal_dict.move_to_end(sig.signal)

    def clear(self):
        """Clear/purge the signal cache."""
        self._signal_dict.clear()

    def replay(self):
        """Replay all cached signals."""
        for (signal, args) in self._signal_dict.values():
            logging.debug('emitting {}'.format(dbg_signal(signal, args)))
            signal.emit(*args)

    def _signal_needs_caching(self, signal):
        """Return True if a signal should be cached, false otherwise."""
        return not signal_name(signal) in self._uncached
