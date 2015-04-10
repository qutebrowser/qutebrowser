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

"""Classes related to auto-updating and getting the latest version."""

import json
import functools

from PyQt5.QtCore import pyqtSignal, QObject, QUrl
from PyQt5.QtNetwork import (QNetworkAccessManager, QNetworkRequest,
                             QNetworkReply)


class PyPIVersionClient(QObject):

    """A client for the PyPI API using QNetworkAccessManager.

    It gets the latest version of qutebrowser from PyPI.

    Attributes:
        _nam: The QNetworkAccessManager used.

    Class attributes:
        API_URL: The base API URL.

    Signals:
        success: Emitted when getting the version info succeeded.
                 arg: The newest version.
        error: Emitted when getting the version info failed.
               arg: The error message, as string.
    """

    API_URL = 'https://pypi.python.org/pypi/{}/json'
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)

    def get_version(self, package='qutebrowser'):
        """Get the newest version of a given package.

        Emits success/error when done.

        Args:
            package: The name of the package to check.
        """
        url = QUrl(self.API_URL.format(package))
        request = QNetworkRequest(url)
        reply = self._nam.get(request)
        if reply.isFinished():
            self.on_reply_finished(reply)
        else:
            reply.finished.connect(functools.partial(
                self.on_reply_finished, reply))

    def on_reply_finished(self, reply):
        """When the reply finished, load and parse the json data.

        Then emits error/success.

        Args:
            reply: The QNetworkReply which finished.
        """
        if reply.error() != QNetworkReply.NoError:
            self.error.emit(reply.errorString())
            return
        try:
            data = bytes(reply.readAll()).decode('utf-8')
        except UnicodeDecodeError as e:
            self.error.emit("Invalid UTF-8 data received in reply: "
                            "{}!".format(e))
            return
        try:
            json_data = json.loads(data)
        except ValueError as e:
            self.error.emit("Invalid JSON received in reply: {}!".format(e))
            return
        try:
            self.success.emit(json_data['info']['version'])
        except KeyError as e:
            self.error.emit("Malformed data recieved in reply "
                            "({!r} not found)!".format(e))
            return
