# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# Based on the Eric5 helpviewer,
# Copyright (c) 2009 - 2014 Detlev Offenbach <detlev@die-offenbachs.de>
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

"""Special network replies.."""

from PyQt5.QtNetwork import QNetworkReply, QNetworkRequest
from PyQt5.QtCore import pyqtSlot, QIODevice, QByteArray, QTimer


class FixedDataNetworkReply(QNetworkReply):

    """QNetworkReply subclass for fixed data."""

    def __init__(self, request, fileData, mimeType, parent=None):
        """Constructor.

        Args:
            request: reference to the request object (QNetworkRequest)
            fileData: reference to the data buffer (QByteArray)
            mimeType: for the reply (string)
            parent: reference to the parent object (QObject)
        """
        super().__init__(parent)

        self._data = fileData

        self.setRequest(request)
        self.setUrl(request.url())
        self.setOpenMode(QIODevice.ReadOnly)

        self.setHeader(QNetworkRequest.ContentTypeHeader, mimeType)
        self.setHeader(QNetworkRequest.ContentLengthHeader,
                       QByteArray.number(len(fileData)))
        self.setAttribute(QNetworkRequest.HttpStatusCodeAttribute, 200)
        self.setAttribute(QNetworkRequest.HttpReasonPhraseAttribute, 'OK')
        # For some reason, a segfault will be triggered if these lambdas aren't
        # there.
        # pylint: disable=unnecessary-lambda
        QTimer.singleShot(0, lambda: self.metaDataChanged.emit())
        QTimer.singleShot(0, lambda: self.readyRead.emit())
        QTimer.singleShot(0, lambda: self.finished.emit())

    @pyqtSlot()
    def abort(self):
        """Abort the operation."""
        pass

    def bytesAvailable(self):
        """Determine the bytes available for being read.

        Return:
            bytes available (int)
        """
        return len(self._data) + super().bytesAvailable()

    def readData(self, maxlen):
        """Retrieve data from the reply object.

        Args:
            maxlen maximum number of bytes to read (int)

        Return:
            bytestring containing the data
        """
        len_ = min(maxlen, len(self._data))
        buf = bytes(self._data[:len_])
        self._data = self._data[len_:]
        return buf

    def isFinished(self):
        return True

    def isRunning(self):
        return False


class ErrorNetworkReply(QNetworkReply):

    """QNetworkReply which always returns an error."""

    def __init__(self, req, errorstring, error, parent=None):
        """Constructor.

        Args:
            req: The QNetworkRequest associated with this reply.
            errorstring: The error string to print.
            error: The numerical error value.
            parent: The parent to pass to QNetworkReply.
        """
        super().__init__(parent)
        self.setRequest(req)
        self.setUrl(req.url())
        # We don't actually want to read anything, but we still need to open
        # the device to avoid getting a warning.
        self.setOpenMode(QIODevice.ReadOnly)
        self.setError(error, errorstring)
        # For some reason, a segfault will be triggered if these lambdas aren't
        # there.
        # pylint: disable=unnecessary-lambda
        QTimer.singleShot(0, lambda: self.error.emit(error))
        QTimer.singleShot(0, lambda: self.finished.emit())

    def abort(self):
        """Do nothing since it's a fake reply."""
        pass

    def bytesAvailable(self):
        """We always have 0 bytes available."""
        return 0

    def readData(self, _maxlen):
        """No data available."""
        return bytes()

    def isFinished(self):
        return True

    def isRunning(self):
        return False
