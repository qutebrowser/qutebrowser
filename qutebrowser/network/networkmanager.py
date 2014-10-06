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

from PyQt5.QtCore import pyqtSlot, PYQT_VERSION, QCoreApplication
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply

try:
    from PyQt5.QtNetwork import QSslSocket
except ImportError:
    SSL_AVAILABLE = False
else:
    SSL_AVAILABLE = QSslSocket.supportsSsl()

from qutebrowser.config import config
from qutebrowser.utils import message, log, usertypes, utils, objreg
from qutebrowser.network import qutescheme, schemehandler


class NetworkManager(QNetworkAccessManager):

    """Our own QNetworkAccessManager.

    Attributes:
        _requests: Pending requests.
        _scheme_handlers: A dictionary (scheme -> handler) of supported custom
                          schemes.
        _win_id: The window ID this NetworkManager is associated with.
    """

    def __init__(self, win_id, parent=None):
        log.init.debug("Initializing NetworkManager")
        super().__init__(parent)
        self._win_id = win_id
        self._requests = []
        self._scheme_handlers = {
            'qute': qutescheme.QuteSchemeHandler(win_id),
        }

        # We have a shared cookie jar and cache - we restore their parents so
        # we don't take ownership of them.
        app = QCoreApplication.instance()
        cookie_jar = objreg.get('cookie-jar')
        self.setCookieJar(cookie_jar)
        cookie_jar.setParent(app)
        cache = objreg.get('cache')
        self.setCache(cache)
        cache.setParent(app)

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
            user, password = answer
            authenticator.setUser(user)
            authenticator.setPassword(password)

    def shutdown(self):
        """Abort all running requests."""
        self.setNetworkAccessible(QNetworkAccessManager.NotAccessible)
        for request in self._requests:
            request.abort()
            request.deleteLater()

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
            # https://github.com/The-Compiler/qutebrowser/issues/114
            message.error(self._win_id,
                          'SSL error: {}'.format(err.errorString()))
        reply.ignoreSslErrors()

    @pyqtSlot('QNetworkReply', 'QAuthenticator')
    def on_authentication_required(self, _reply, authenticator):
        """Called when a website needs authentication."""
        answer = message.ask(self._win_id,
                             "Username ({}):".format(authenticator.realm()),
                             mode=usertypes.PromptMode.user_pwd)
        self._fill_authenticator(authenticator, answer)

    @pyqtSlot('QNetworkProxy', 'QAuthenticator')
    def on_proxy_authentication_required(self, _proxy, authenticator):
        """Called when a proxy needs authentication."""
        answer = message.ask(self._win_id, "Proxy username ({}):".format(
            authenticator.realm()), mode=usertypes.PromptMode.user_pwd)
        self._fill_authenticator(authenticator, answer)

    # WORKAROUND for:
    # http://www.riverbankcomputing.com/pipermail/pyqt/2014-September/034806.html
    #
    # By returning False, we provoke a TypeError because of a wrong return
    # type, which does *not* trigger a segfault but invoke our return handler
    # immediately.
    @utils.prevent_exceptions(False)
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
            return schemehandler.ErrorNetworkReply(
                req, "SSL is not supported by the installed Qt library!",
                QNetworkReply.ProtocolUnknownError)
        elif scheme in self._scheme_handlers:
            return self._scheme_handlers[scheme].createRequest(
                op, req, outgoing_data)
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
        if PYQT_VERSION < 0x050301:
            # WORKAROUND (remove this when we bump the requirements to 5.3.1)
            #
            # If we don't disable our message handler, we get a freeze if a
            # warning is printed due to a PyQt bug, e.g. when clicking a
            # currency on http://ch.mouser.com/localsites/
            #
            # See http://www.riverbankcomputing.com/pipermail/pyqt/2014-June/034420.html
            with log.disable_qt_msghandler():
                reply = super().createRequest(op, req, outgoing_data)
        else:
            reply = super().createRequest(op, req, outgoing_data)
        self._requests.append(reply)
        reply.destroyed.connect(lambda obj: self._requests.remove(obj))
        return reply
