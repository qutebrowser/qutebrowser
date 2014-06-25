# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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
from PyQt5.QtNetwork import (QNetworkAccessManager, QNetworkReply,
                             QNetworkRequest)

try:
    from PyQt5.QtNetwork import QSslSocket
except ImportError:
    SSL_AVAILABLE = False
else:
    SSL_AVAILABLE = QSslSocket.supportsSsl()

import qutebrowser.config.config as config
import qutebrowser.utils.message as message
import qutebrowser.utils.log as log
from qutebrowser.network.qutescheme import QuteSchemeHandler
from qutebrowser.network.schemehandler import ErrorNetworkReply
from qutebrowser.utils.usertypes import PromptMode


class NetworkManager(QNetworkAccessManager):

    """Our own QNetworkAccessManager.

    Attributes:
        _requests: Pending requests.
        _scheme_handlers: A dictionary (scheme -> handler) of supported custom
                          schemes.
    """

    def __init__(self, cookiejar=None, parent=None):
        log.init.debug("Initializing NetworkManager")
        super().__init__(parent)
        self._requests = []
        self._scheme_handlers = {
            'qute': QuteSchemeHandler(),
        }
        if cookiejar is not None:
            self.setCookieJar(cookiejar)
        if SSL_AVAILABLE:
            self.sslErrors.connect(self.on_ssl_errors)
        self.authenticationRequired.connect(self.on_authentication_required)
        self.proxyAuthenticationRequired.connect(
            self.on_proxy_authentication_required)
        log.init.debug("NetworkManager init done")

    def _fill_authenticator(self, authenticator, answer):
        """Fill a given QAuthenticator object with an answer."""
        if answer is not None:
            # Since the answer could be something else than (user, password)
            # pylint seems to think we're unpacking a non-sequence. However we
            # *did* explicitely ask for a tuple, so it *will* always be one.
            user, password = answer  # pylint: disable=unpacking-non-sequence
            authenticator.setUser(user)
            authenticator.setPassword(password)

    def abort_requests(self):
        """Abort all running requests."""
        for request in self._requests:
            request.abort()

    @pyqtSlot('QNetworkReply*', 'QList<QSslError>')
    def on_ssl_errors(self, reply, errors):
        """Decide if SSL errors should be ignored or not.

        This slot is called on SSL/TLS errors by the self.sslErrors signal.

        Args:
            reply: The QNetworkReply that is encountering the errors.
            errors: A list of errors.
        """
        if config.get('network', 'ssl-strict'):
            return
        for err in errors:
            # FIXME we might want to use warn here (non-fatal error)
            message.error('SSL error: {}'.format(err.errorString()),
                          queue=True)
        reply.ignoreSslErrors()

    @pyqtSlot('QNetworkReply', 'QAuthenticator')
    def on_authentication_required(self, _reply, authenticator):
        """Called when a website needs authentication."""
        answer = message.modular_question(
            "Username ({}):".format(authenticator.realm()),
            mode=PromptMode.user_pwd)
        self._fill_authenticator(authenticator, answer)

    @pyqtSlot('QNetworkProxy', 'QAuthenticator')
    def on_proxy_authentication_required(self, _proxy, authenticator):
        """Called when a proxy needs authentication."""
        answer = message.modular_question(
            "Proxy username ({}):".format(authenticator.realm()),
            mode=PromptMode.user_pwd)
        self._fill_authenticator(authenticator, answer)

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
        if scheme == 'https' and not SSL_AVAILABLE:
            return ErrorNetworkReply(
                req, "SSL is not supported by the installed Qt library!",
                QNetworkReply.ProtocolUnknownError)
        elif scheme in self._scheme_handlers:
            return self._scheme_handlers[scheme].createRequest(
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
            with log.disable_qt_msghandler():
                # If we don't disable our message handler, we get a freeze on
                # http://ch.mouser.com/localsites/ when clicking on a currency.
                #
                # FIXME: Open questions:
                #
                #   - Shouldn't QtWebPage set the content-type correctly by
                #     itself?
                #
                #   - Why does Qt freeze if we don't disable our message
                #     handler?
                reply = super().createRequest(op, req, outgoing_data)
            self._requests.append(reply)
            reply.destroyed.connect(lambda obj: self._requests.remove(obj))
        return reply
