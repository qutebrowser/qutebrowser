# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Our own QKeySequence-like class and related utilities."""

from PyQt5.QtGui import QKeySequence

from qutebrowser.utils import utils


class KeySequence:

    def __init__(self, *args):
        self._sequence = QKeySequence(*args)

    def __str__(self):
        return self._sequence.toString()

    def __repr__(self):
        return utils.get_repr(self, keys=str(self))

    def __lt__(self, other):
        return self._sequence < other._sequence

    def __gt__(self, other):
        return self._sequence > other._sequence

    def __eq__(self, other):
        return self._sequence == other._sequence

    def __ne__(self, other):
        return self._sequence != other._sequence

    def __hash__(self):
        return hash(self._sequence)

    def matches(self, other):
        # pylint: disable=protected-access
        return self._sequence.matches(other._sequence)

    def append_event(self, ev):
        return self.__class__(*self._sequence, ev.modifiers() | ev.key())
