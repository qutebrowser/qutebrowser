# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Client for the pastebin."""

import urllib.parse

from qutebrowser.qt.core import pyqtSignal, pyqtSlot, QObject, QUrl


class PastebinClient(QObject):

    """A client for Stikked pastebins using HTTPClient.

    Attributes:
        _client: The HTTPClient used.

    Class attributes:
        API_URL: The base API URL.

    Signals:
        success: Emitted when the paste succeeded.
                 arg: The URL of the paste, as string.
        error: Emitted when the paste failed.
               arg: The error message, as string.
    """

    API_URL = 'https://crashes.qutebrowser.org/api/'
    MISC_API_URL = 'https://paste.the-compiler.org/api/'
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, client, parent=None, api_url=API_URL):
        """Constructor.

        Args:
            client: The HTTPClient to use. Will be reparented.
            api_url: The Stikked pastebin endpoint to use.
        """
        super().__init__(parent)
        client.setParent(self)
        client.error.connect(self.error)
        client.success.connect(self.on_client_success)
        self._client = client
        self._api_url = api_url

    def paste(self, name, title, text, parent=None, private=False):
        """Paste the text into a pastebin and return the URL.

        Args:
            name: The username to post as.
            title: The post title.
            text: The text to post.
            parent: The parent paste to reply to.
            private: Whether to paste privately.
        """
        data = {
            'text': text,
            'title': title,
            'name': name,
            'apikey': 'ihatespam',
        }
        if parent is not None:
            data['reply'] = parent
        if private:
            data['private'] = '1'

        url = QUrl(urllib.parse.urljoin(self._api_url, 'create'))
        self._client.post(url, data)

    @pyqtSlot(str)
    def on_client_success(self, data):
        """Process the data and finish when the client finished.

        Args:
            data: A string with the received data.
        """
        if data.startswith('http://') or data.startswith('https://'):
            self.success.emit(data)
        else:
            self.error.emit("Invalid data received in reply!")
