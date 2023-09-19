# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""QtWebKit specific part of history."""

import functools

# pylint: disable=no-name-in-module
from qutebrowser.qt.webkit import QWebHistoryInterface
# pylint: enable=no-name-in-module

from qutebrowser.utils import debug
from qutebrowser.misc import debugcachestats


class WebHistoryInterface(QWebHistoryInterface):

    """Glue code between WebHistory and Qt's QWebHistoryInterface.

    Attributes:
        _history: The WebHistory object.
    """

    def __init__(self, webhistory, parent=None):
        super().__init__(parent)
        self._history = webhistory
        self._history.changed.connect(self.historyContains.cache_clear)

    def addHistoryEntry(self, url_string):
        """Required for a QWebHistoryInterface impl, obsoleted by add_url."""

    @debugcachestats.register(name='history')
    @functools.lru_cache(maxsize=32768)  # noqa: B019
    def historyContains(self, url_string):
        """Called by WebKit to determine if a URL is contained in the history.

        Args:
            url_string: The URL (as string) to check for.

        Return:
            True if the url is in the history, False otherwise.
        """
        with debug.log_time('sql', 'historyContains'):
            return url_string in self._history


def init(history):
    """Initialize the QWebHistoryInterface.

    Args:
        history: The WebHistory object.
    """
    interface = WebHistoryInterface(history, parent=history)
    QWebHistoryInterface.setDefaultInterface(interface)
