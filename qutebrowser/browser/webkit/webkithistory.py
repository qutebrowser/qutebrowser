# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""QtWebKit specific part of history."""


from PyQt5.QtWebKit import QWebHistoryInterface


class WebHistoryInterface(QWebHistoryInterface):

    """Glue code between WebHistory and Qt's QWebHistoryInterface.

    Attributes:
        _history: The WebHistory object.
    """

    def __init__(self, webhistory, parent=None):
        super().__init__(parent)
        self._history = webhistory

    def addHistoryEntry(self, url_string):
        """Required for a QWebHistoryInterface impl, obsoleted by add_url."""
        pass

    def historyContains(self, url_string):
        """Called by WebKit to determine if a URL is contained in the history.

        Args:
            url_string: The URL (as string) to check for.

        Return:
            True if the url is in the history, False otherwise.
        """
        return url_string in self._history.history_dict


def init(history):
    """Initialize the QWebHistoryInterface.

    Args:
        history: The WebHistory object.
    """
    interface = WebHistoryInterface(history, parent=history)
    QWebHistoryInterface.setDefaultInterface(interface)
