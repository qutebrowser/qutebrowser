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
    """Get a cleaned up name of a signal.

    Args:
        sig: The pyqtSignal

    Return:
        The cleaned up signal name.
    """
    m = re.match(r'[0-9]+(.*)\(.*\)', sig.signal)
    return m.group(1)


def dbg_signal(sig, args):
    """Get a string representation of a signal for debugging.

    Args:
        sig: A pyqtSignal.
        args: The arguments as list of strings.

    Return:
        A human-readable string representation of signal/args.
    """
    return '{}({})'.format(signal_name(sig), ', '.join(map(str, args)))
