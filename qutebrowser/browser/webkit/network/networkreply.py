# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Based on the Eric5 helpviewer,
# Copyright (c) 2009 - 2014 Detlev Offenbach <detlev@die-offenbachs.de>

"""Special network replies.."""

from qutebrowser.qt.network import QNetworkReply, QNetworkRequest
from qutebrowser.qt.core import pyqtSlot, QIODevice, QByteArray, QTimer


class FixedDataNetworkReply(QNetworkReply):

    """QNetworkReply subclass for fixed data."""

    def __init__(self, request, fileData, mimeType, parent=None):  # noqa: N803
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
        self.setOpenMode(QIODevice.OpenModeFlag.ReadOnly)

        self.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, mimeType)
        self.setHeader(QNetworkRequest.KnownHeaders.ContentLengthHeader,
                       QByteArray.number(len(fileData)))
        self.setAttribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute, 200)
        self.setAttribute(QNetworkRequest.Attribute.HttpReasonPhraseAttribute, 'OK')
        # For some reason, a segfault will be triggered if these lambdas aren't
        # there.
        # pylint: disable=unnecessary-lambda
        QTimer.singleShot(0, lambda: self.metaDataChanged.emit())
        QTimer.singleShot(0, lambda: self.readyRead.emit())
        QTimer.singleShot(0, lambda: self.finished.emit())

    @pyqtSlot()
    def abort(self):
        """Abort the operation."""

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
        self.setOpenMode(QIODevice.OpenModeFlag.ReadOnly)
        self.setError(error, errorstring)
        QTimer.singleShot(0, lambda: self.errorOccurred.emit(error))
        # pylint: disable-next=unnecessary-lambda
        QTimer.singleShot(0, lambda: self.finished.emit())

    def abort(self):
        """Do nothing since it's a fake reply."""

    def bytesAvailable(self):
        """We always have 0 bytes available."""
        return 0

    def readData(self, _maxlen):
        """No data available."""
        return b''

    def isFinished(self):
        return True

    def isRunning(self):
        return False


class RedirectNetworkReply(QNetworkReply):

    """A reply which redirects to the given URL."""

    def __init__(self, new_url, parent=None):
        super().__init__(parent)
        self.setAttribute(QNetworkRequest.Attribute.RedirectionTargetAttribute, new_url)
        # pylint: disable-next=unnecessary-lambda
        QTimer.singleShot(0, lambda: self.finished.emit())

    def abort(self):
        """Called when there's e.g. a redirection limit."""

    def readData(self, _maxlen):
        return b''
