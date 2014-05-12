# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Our own QNetworkAccessManager."""

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtNetwork import QNetworkAccessManager

import qutebrowser.config.config as config
import qutebrowser.utils.message as message
from qutebrowser.network.qutescheme import QuteSchemeHandler


class NetworkManager(QNetworkAccessManager):

    """Our own QNetworkAccessManager.

    Attributes:
        _requests: Pending requests.
        _scheme_handlers: A dictionary (scheme -> handler) of supported custom
                          schemes.
    """

    def __init__(self, cookiejar=None, parent=None):
        super().__init__(parent)
        self._requests = {}
        self._scheme_handlers = {
            'qute': QuteSchemeHandler(),
        }
        if cookiejar is not None:
            self.setCookieJar(cookiejar)
        self.sslErrors.connect(self.on_ssl_errors)

    def abort_requests(self):
        """Abort all running requests."""
        for request in self._requests.values():
            request.abort()

    @pyqtSlot('QNetworkReply', 'QList<QSslError>')
    def on_ssl_errors(self, reply, errors):
        """This slot is called on SSL/TLS errors.

        Args:
            reply: The QNetworkReply that is encountering the errors.
            errors: A list of errors.
        """
        if config.get('network', 'ssl-strict'):
            return
        for err in errors:
            message.error('SSL error: {}'.format(err.errorString()))
        reply.ignoreSslErrors()


    def createRequest(self, op, req, outgoing_data):
        """Return a new QNetworkReply object.

        Extend QNetworkAccessManager::createRequest to save requests in
        self._requests and handle custom schemes.

        Args:
             op: Operation op
             req: const QNetworkRequest & req
             outgoing_data: QIODevice * outgoingData

        Return:
            A QNetworkReply.
        """
        scheme = req.url().scheme()
        if scheme in self._scheme_handlers:
            reply = self._scheme_handlers[scheme].createRequest(
                op, req, outgoing_data)
        else:
            if config.get('network', 'do-not-track'):
                dnt = '1'.encode('ascii')
            else:
                dnt = '0'.encode('ascii')
            req.setRawHeader('DNT'.encode('ascii'), dnt)
            req.setRawHeader('X-Do-Not-Track'.encode('ascii'), dnt)
            accept_language = config.get('network', 'accept-language')
            if accept_language is not None:
                req.setRawHeader('Accept-Language'.encode('ascii'),
                                 accept_language.encode('ascii'))
            reply = super().createRequest(op, req, outgoing_data)
            self._requests[id(reply)] = reply
            reply.destroyed.connect(lambda obj: self._requests.pop(id(obj)))
        return reply
