# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""The search match indicator in the statusbar."""


from PyQt5.QtCore import pyqtSlot

from qutebrowser.utils import log
from qutebrowser.browser import browsertab
from qutebrowser.mainwindow.statusbar import textbase


class SearchMatch(textbase.TextBase):

    """The part of the statusbar that displays the search match counter."""

    @pyqtSlot(browsertab.SearchMatch)
    def set_match(self, match: browsertab.SearchMatch) -> None:
        """Set the match counts in the statusbar.

        Passing SearchMatch(0, 0) hides the match counter.

        Args:
            match: The currently active search match.
        """
        if match.current <= 0 and match.total <= 0:
            self.setText('')
            log.statusbar.debug('Clearing search match text.')
        else:
            self.setText(f'Match [{match}]')
            log.statusbar.debug(f'Setting search match text to {match}')
