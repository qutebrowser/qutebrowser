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

import functools
import urllib.request
import urllib.parse

from PyQt5.QtCore import pyqtSignal, QObject, QUrl
from PyQt5.QtNetwork import (QNetworkAccessManager, QNetworkRequest,
                             QNetworkReply)


class PastebinClient(QObject):

    """A client for http://p.cmpl.cc/ using QNetworkAccessManager.

    Attributes:
        _nam: The QNetworkAccessManager used.

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
        self._nam = QNetworkAccessManager(self)

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
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        create_url = urllib.parse.urljoin(self.API_URL, 'create')
        request = QNetworkRequest(QUrl(create_url))
        request.setHeader(QNetworkRequest.ContentTypeHeader,
                          'application/x-www-form-urlencoded;charset=utf-8')
        reply = self._nam.post(request, encoded_data)
        if reply.isFinished():
            self.on_reply_finished(reply)
        else:
            reply.finished.connect(functools.partial(
                self.on_reply_finished, reply))

    def on_reply_finished(self, reply):
        """Read the data and finish when the reply finished.

        Args:
            reply: The QNetworkReply which finished.
        """
        if reply.error() != QNetworkReply.NoError:
            self.error.emit(reply.errorString())
            return
        try:
            url = bytes(reply.readAll()).decode('utf-8')
        except UnicodeDecodeError:
            self.error.emit("Invalid UTF-8 data received in reply!")
            return
        if url.startswith('http://'):
            self.success.emit(url)
        else:
            self.error.emit("Invalid data received in reply!")
