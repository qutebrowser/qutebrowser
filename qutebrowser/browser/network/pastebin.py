# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Client for the pastebin."""

import urllib.parse

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QUrl

from qutebrowser.misc import httpclient


class PastebinClient(QObject):

    """A client for http://p.cmpl.cc/ using HTTPClient.

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

    API_URL = 'http://paste.the-compiler.org/api/'
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = httpclient.HTTPClient(self)
        self._client.error.connect(self.error)
        self._client.success.connect(self.on_client_success)

    def paste(self, name, title, text, parent=None):
        """Paste the text into a pastebin and return the URL.

        Args:
            name: The username to post as.
            title: The post title.
            text: The text to post.
            parent: The parent paste to reply to.
        """
        data = {
            'text': text,
            'title': title,
            'name': name,
        }
        if parent is not None:
            data['reply'] = parent
        url = QUrl(urllib.parse.urljoin(self.API_URL, 'create'))
        self._client.post(url, data)

    @pyqtSlot(str)
    def on_client_success(self, data):
        """Process the data and finish when the client finished.

        Args:
            data: A string with the received data.
        """
        if data.startswith('http://'):
            self.success.emit(data)
        else:
            self.error.emit("Invalid data received in reply!")
