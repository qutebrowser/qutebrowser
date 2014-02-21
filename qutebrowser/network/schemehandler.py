# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Base class for custom scheme handlers."""

import logging

from PyQt5.QtNetwork import QNetworkReply, QNetworkRequest
from PyQt5.QtCore import pyqtSlot, QObject, QIODevice, QByteArray

class SchemeHandler(QObject):

    """Abstract base class for custom scheme handlers."""

    def createRequest(self, op, request, outgoingData=None):
        """Create a new request.

        Args:
             op: Operation op
             req: const QNetworkRequest & req
             outgoing_data: QIODevice * outgoingData

        Return:
            A QNetworkReply.

        Raise:
            NotImplementedError because this needs to be overwritten by
            subclasses.
        """
        raise NotImplementedError



class SpecialNetworkReply(QNetworkReply):

    """QNetworkReply subclass for special data."""

    def __init__(self, request, fileData, mimeType, parent=None):
        """Constructor.

        Args:
            request: reference to the request object (QNetworkRequest)
            fileData: reference to the data buffer (QByteArray)
            mimeType: for the reply (string)
            parent: reference to the parent object (QObject)

        Emit:
            metaDataChanged and readyRead and finished after initializing.

        """
        super().__init__(parent)

        self._data = fileData

        self.setRequest(request)
        self.setOpenMode(QIODevice.ReadOnly)

        self.setHeader(QNetworkRequest.ContentTypeHeader, mimeType)
        self.setHeader(QNetworkRequest.ContentLengthHeader,
                       QByteArray.number(fileData.length()))
        self.setAttribute(QNetworkRequest.HttpStatusCodeAttribute, 200)
        self.setAttribute(QNetworkRequest.HttpReasonPhraseAttribute, "OK")
        self.metaDataChanged.emit()
        self.readyRead.emit()
        self.finished.emit()

    @pyqtSlot()
    def abort(self):
        """Abort the operation."""
        pass

    def bytesAvailable(self):
        """Determine the bytes available for being read.

        Return:
            bytes available (int)

        """
        return self._data.length() + super().bytesAvailable()
        logging.debug("bytes available: {}".format(len(self._data)))

    def readData(self, maxlen):
        """Retrieve data from the reply object.

        Args:
            maxlen maximum number of bytes to read (int)

        Return:
            bytestring containing the data

        """
        len_ = min(maxlen, self._data.length())
        buf = bytes(self._data[:len_])
        self._data.remove(0, len_)
        logging.debug("readdata, len {}, maxlen {}, buf {}".format(len(self._data), maxlen, buf))
        return buf
