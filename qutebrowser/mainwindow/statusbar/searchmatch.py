# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The search match indicator in the statusbar."""


from qutebrowser.qt.core import pyqtSlot

from qutebrowser.browser import browsertab
from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import log


class SearchMatch(textbase.TextBase):

    """The part of the statusbar that displays the search match counter."""

    @pyqtSlot(browsertab.SearchMatch)
    def set_match(self, search_match: browsertab.SearchMatch) -> None:
        """Set the match counts in the statusbar.

        Passing SearchMatch(0, 0) hides the match counter.

        Args:
            search_match: The currently active search match.
        """
        if search_match.is_null():
            self.setText('')
            log.statusbar.debug('Clearing search match text.')
        else:
            self.setText(f'Match [{search_match}]')
            log.statusbar.debug(f'Setting search match text to {search_match}')
