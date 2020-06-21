# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QUrl

from qutebrowser.misc import httpclient


class PyPIVersionClient(QObject):

    """A client for the PyPI API using HTTPClient.

    It gets the latest version of qutebrowser from PyPI.

    Attributes:
        _client: The HTTPClient used.

    Class attributes:
        API_URL: The base API URL.

    Signals:
        success: Emitted when getting the version info succeeded.
                 arg: The newest version.
        error: Emitted when getting the version info failed.
               arg: The error message, as string.
    """

    API_URL = 'https://pypi.org/pypi/{}/json'
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None, client=None):
        super().__init__(parent)
        if client is None:
            self._client = httpclient.HTTPClient(self)
        else:
            self._client = client
        self._client.error.connect(self.error)  # type: ignore[arg-type]
        self._client.success.connect(self.on_client_success)

    def get_version(self, package='qutebrowser'):
        """Get the newest version of a given package.

        Emits success/error when done.

        Args:
            package: The name of the package to check.
        """
        url = QUrl(self.API_URL.format(package))
        self._client.get(url)

    @pyqtSlot(str)
    def on_client_success(self, data):
        """Process the data and finish when the client finished.

        Args:
            data: A string with the received data.
        """
        try:
            json_data = json.loads(data)
        except ValueError as e:
            self.error.emit("Invalid JSON received in reply: {}!".format(e))
            return
        try:
            self.success.emit(json_data['info']['version'])
        except KeyError as e:
            self.error.emit("Malformed data received in reply "
                            "({!r} not found)!".format(e))
            return
