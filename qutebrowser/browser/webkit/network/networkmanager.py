# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os
import collections
import netrc
import html

from PyQt5.QtCore import (pyqtSlot, pyqtSignal, PYQT_VERSION, QCoreApplication,
                          QUrl, QByteArray)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QSslSocket

from qutebrowser.config import config
from qutebrowser.utils import (message, log, usertypes, utils, objreg, qtutils,
                               urlutils)
from qutebrowser.browser import shared
from qutebrowser.browser.webkit import certificateerror
from qutebrowser.browser.webkit.network import (webkitqutescheme, networkreply,
                                                filescheme)


HOSTBLOCK_ERROR_STRING = '%HOSTBLOCK%'
ProxyId = collections.namedtuple('ProxyId', 'type, hostname, port')
_proxy_auth_cache = {}


def _is_secure_cipher(cipher):
    """Check if a given SSL cipher (hopefully) isn't broken yet."""
    tokens = [e.upper() for e in cipher.name().split('-')]
    if cipher.usedBits() < 128:
        # https://codereview.qt-project.org/#/c/75943/
        return False
    # OpenSSL should already protect against this in a better way
    elif cipher.keyExchangeMethod() == 'DH' and os.name == 'nt':
        # https://weakdh.org/
        return False
    elif cipher.encryptionMethod().upper().startswith('RC4'):
        # http://en.wikipedia.org/wiki/RC4#Security
        # https://codereview.qt-project.org/#/c/148906/
        return False
    elif cipher.encryptionMethod().upper().startswith('DES'):
        # http://en.wikipedia.org/wiki/Data_Encryption_Standard#Security_and_cryptanalysis
        return False
    elif 'MD5' in tokens:
        # http://www.win.tue.nl/hashclash/rogue-ca/
        return False
    # OpenSSL should already protect against this in a better way
    # elif (('CBC3' in tokens or 'CBC' in tokens) and (cipher.protocol() not in
    #         [QSsl.TlsV1_0, QSsl.TlsV1_1, QSsl.TlsV1_2])):
    #     # http://en.wikipedia.org/wiki/POODLE
    #     return False
    ### These things should never happen as those are already filtered out by
    ### either the SSL libraries or Qt - but let's be sure.
    elif cipher.authenticationMethod() in ['aNULL', 'NULL']:
        # Ciphers without authentication.
        return False
    elif cipher.encryptionMethod() in ['eNULL', 'NULL']:
        # Ciphers without encryption.
        return False
    elif 'EXP' in tokens or 'EXPORT' in tokens:
        # Weak export-grade ciphers
        return False
    elif 'ADH' in tokens:
        # No MITM protection
        return False
    ### This *should* happen ;)
    else:
        return True


def init():
    """Disable insecure SSL ciphers on old Qt versions."""
    if qtutils.version_check('5.3.0'):
        default_ciphers = QSslSocket.defaultCiphers()
        log.init.debug("Default Qt ciphers: {}".format(
            ', '.join(c.name() for c in default_ciphers)))
    else:
        # https://codereview.qt-project.org/#/c/75943/
        default_ciphers = QSslSocket.supportedCiphers()
        log.init.debug("Supported Qt ciphers: {}".format(
            ', '.join(c.name() for c in default_ciphers)))

    good_ciphers = []
    bad_ciphers = []
    for cipher in default_ciphers:
        if _is_secure_cipher(cipher):
            good_ciphers.append(cipher)
        else:
            bad_ciphers.append(cipher)

    log.init.debug("Disabling bad ciphers: {}".format(
        ', '.join(c.name() for c in bad_ciphers)))
    QSslSocket.setDefaultCiphers(good_ciphers)


class NetworkManager(QNetworkAccessManager):

    """Our own QNetworkAccessManager.

    Attributes:
        adopted_downloads: If downloads are running with this QNAM but the
                           associated tab gets closed already, the NAM gets
                           reparented to the DownloadManager. This counts the
                           still running downloads, so the QNAM can clean
                           itself up when this reaches zero again.
        _requests: Pending requests.
        _scheme_handlers: A dictionary (scheme -> handler) of supported custom
                          schemes.
        _win_id: The window ID this NetworkManager is associated with.
        _tab_id: The tab ID this NetworkManager is associated with.
        _rejected_ssl_errors: A {QUrl: [SslError]} dict of rejected errors.
        _accepted_ssl_errors: A {QUrl: [SslError]} dict of accepted errors.

    Signals:
        shutting_down: Emitted when the QNAM is shutting down.
    """

    shutting_down = pyqtSignal()

    def __init__(self, win_id, tab_id, parent=None):
        log.init.debug("Initializing NetworkManager")
        with log.disable_qt_msghandler():
            # WORKAROUND for a hang when a message is printed - See:
            # http://www.riverbankcomputing.com/pipermail/pyqt/2014-November/035045.html
            super().__init__(parent)
        log.init.debug("NetworkManager init done")
        self.adopted_downloads = 0
        self._win_id = win_id
        self._tab_id = tab_id
        self._requests = []
        self._scheme_handlers = {
            'qute': webkitqutescheme.QuteSchemeHandler(win_id),
            'file': filescheme.FileSchemeHandler(win_id),
        }
        self._set_cookiejar(private=config.get('general', 'private-browsing'))
        self._set_cache()
        self.sslErrors.connect(self.on_ssl_errors)
        self._rejected_ssl_errors = collections.defaultdict(list)
        self._accepted_ssl_errors = collections.defaultdict(list)
        self.authenticationRequired.connect(self.on_authentication_required)
        self.proxyAuthenticationRequired.connect(
            self.on_proxy_authentication_required)
        objreg.get('config').changed.connect(self.on_config_changed)

    def _set_cookiejar(self, private=False):
        """Set the cookie jar of the NetworkManager correctly.

        Args:
            private: Whether we're currently in private browsing mode.
        """
        if private:
            cookie_jar = objreg.get('ram-cookie-jar')
        else:
            cookie_jar = objreg.get('cookie-jar')

        # We have a shared cookie jar - we restore its parent so we don't
        # take ownership of it.
        self.setCookieJar(cookie_jar)
        app = QCoreApplication.instance()
        cookie_jar.setParent(app)

    def _set_cache(self):
        """Set the cache of the NetworkManager correctly.

        We can't switch the whole cache in private mode because QNAM would
        delete the old cache.
        """
        # We have a shared cache - we restore its parent so we don't take
        # ownership of it.
        app = QCoreApplication.instance()
        cache = objreg.get('cache')
        self.setCache(cache)
        cache.setParent(app)

    def _get_abort_signals(self, owner=None):
        """Get a list of signals which should abort a question."""
        abort_on = [self.shutting_down]
        if owner is not None:
            abort_on.append(owner.destroyed)
        # This might be a generic network manager, e.g. one belonging to a
        # DownloadManager. In this case, just skip the webview thing.
        if self._tab_id is not None:
            tab = objreg.get('tab', scope='tab', window=self._win_id,
                             tab=self._tab_id)
            abort_on.append(tab.load_started)
        return abort_on

    def shutdown(self):
        """Abort all running requests."""
        self.setNetworkAccessible(QNetworkAccessManager.NotAccessible)
        for request in self._requests:
            request.abort()
            request.deleteLater()
        self.shutting_down.emit()

    @pyqtSlot('QNetworkReply*', 'QList<QSslError>')
    def on_ssl_errors(self, reply, errors):  # pragma: no mccabe
        """Decide if SSL errors should be ignored or not.

        This slot is called on SSL/TLS errors by the self.sslErrors signal.

        Args:
            reply: The QNetworkReply that is encountering the errors.
            errors: A list of errors.
        """
        errors = [certificateerror.CertificateErrorWrapper(e) for e in errors]
        log.webview.debug("Certificate errors: {!r}".format(
            ' / '.join(str(err) for err in errors)))
        try:
            host_tpl = urlutils.host_tuple(reply.url())
        except ValueError:
            host_tpl = None
            is_accepted = False
            is_rejected = False
        else:
            is_accepted = set(errors).issubset(
                self._accepted_ssl_errors[host_tpl])
            is_rejected = set(errors).issubset(
                self._rejected_ssl_errors[host_tpl])

        log.webview.debug("Already accepted: {} / "
                          "rejected {}".format(is_accepted, is_rejected))

        if is_rejected:
            return
        elif is_accepted:
            reply.ignoreSslErrors()
            return

        abort_on = self._get_abort_signals(reply)
        ignore = shared.ignore_certificate_errors(reply.url(), errors,
                                                  abort_on=abort_on)
        if ignore:
            reply.ignoreSslErrors()
            err_dict = self._accepted_ssl_errors
        else:
            err_dict = self._rejected_ssl_errors
        if host_tpl is not None:
            err_dict[host_tpl] += errors

    def clear_all_ssl_errors(self):
        """Clear all remembered SSL errors."""
        self._accepted_ssl_errors.clear()
        self._rejected_ssl_errors.clear()

    @pyqtSlot(QUrl)
    def clear_rejected_ssl_errors(self, url):
        """Clear the rejected SSL errors on a reload.

        Args:
            url: The URL to remove.
        """
        try:
            del self._rejected_ssl_errors[url]
        except KeyError:
            pass

    @pyqtSlot('QNetworkReply*', 'QAuthenticator*')
    def on_authentication_required(self, reply, authenticator):
        """Called when a website needs authentication."""
        user, password = None, None
        if not hasattr(reply, "netrc_used") and 'HOME' in os.environ:
            # We'll get an OSError by netrc if 'HOME' isn't available in
            # os.environ. We don't want to log that, so we prevent it
            # altogether.
            reply.netrc_used = True
            try:
                net = netrc.netrc(config.get('network', 'netrc-file'))
                authenticators = net.authenticators(reply.url().host())
                if authenticators is not None:
                    (user, _account, password) = authenticators
            except FileNotFoundError:
                log.misc.debug("No .netrc file found")
            except OSError:
                log.misc.exception("Unable to read the netrc file")
            except netrc.NetrcParseError:
                log.misc.exception("Error when parsing the netrc file")

        if user is not None:
            authenticator.setUser(user)
            authenticator.setPassword(password)
        else:
            abort_on = self._get_abort_signals(reply)
            shared.authentication_required(reply.url(), authenticator,
                                           abort_on=abort_on)

    @pyqtSlot('QNetworkProxy', 'QAuthenticator*')
    def on_proxy_authentication_required(self, proxy, authenticator):
        """Called when a proxy needs authentication."""
        proxy_id = ProxyId(proxy.type(), proxy.hostName(), proxy.port())
        if proxy_id in _proxy_auth_cache:
            user, password = _proxy_auth_cache[proxy_id]
            authenticator.setUser(user)
            authenticator.setPassword(password)
        else:
            msg = '<b>{}</b> says:<br/>{}'.format(
                html.escape(proxy.hostName()),
                html.escape(authenticator.realm()))
            abort_on = self._get_abort_signals()
            answer = message.ask(
                title="Proxy authentication required", text=msg,
                mode=usertypes.PromptMode.user_pwd, abort_on=abort_on)
            if answer is not None:
                authenticator.setUser(answer.user)
                authenticator.setPassword(answer.password)
                _proxy_auth_cache[proxy_id] = answer

    @config.change_filter('general', 'private-browsing')
    def on_config_changed(self):
        """Set cookie jar when entering/leaving private browsing mode."""
        private_browsing = config.get('general', 'private-browsing')
        if private_browsing:
            # switched from normal mode to private mode
            self._set_cookiejar(private=True)
        else:
            # switched from private mode to normal mode
            self._set_cookiejar()

    @pyqtSlot()
    def on_adopted_download_destroyed(self):
        """Check if we can clean up if an adopted download was destroyed.

        See the description for adopted_downloads for details.
        """
        self.adopted_downloads -= 1
        log.downloads.debug("Adopted download destroyed, {} left.".format(
            self.adopted_downloads))
        assert self.adopted_downloads >= 0
        if self.adopted_downloads == 0:
            self.deleteLater()

    @pyqtSlot(object)  # DownloadItem
    def adopt_download(self, download):
        """Adopt a new DownloadItem."""
        self.adopted_downloads += 1
        log.downloads.debug("Adopted download, {} adopted.".format(
            self.adopted_downloads))
        download.destroyed.connect(self.on_adopted_download_destroyed)
        download.adopt_download.connect(self.adopt_download)

    def set_referer(self, req, current_url):
        """Set the referer header."""
        referer_header_conf = config.get('network', 'referer-header')

        try:
            if referer_header_conf == 'never':
                # Note: using ''.encode('ascii') sends a header with no value,
                # instead of no header at all
                req.setRawHeader('Referer'.encode('ascii'), QByteArray())
            elif (referer_header_conf == 'same-domain' and
                  not urlutils.same_domain(req.url(), current_url)):
                req.setRawHeader('Referer'.encode('ascii'), QByteArray())
            # If refer_header_conf is set to 'always', we leave the header
            # alone as QtWebKit did set it.
        except urlutils.InvalidUrlError:
            # req.url() or current_url can be invalid - this happens on
            # https://www.playstation.com/ for example.
            pass

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
        proxy_factory = objreg.get('proxy-factory', None)
        if proxy_factory is not None:
            proxy_error = proxy_factory.get_error()
            if proxy_error is not None:
                return networkreply.ErrorNetworkReply(
                    req, proxy_error, QNetworkReply.UnknownProxyError,
                    self)

        scheme = req.url().scheme()
        if scheme in self._scheme_handlers:
            result = self._scheme_handlers[scheme].createRequest(
                op, req, outgoing_data)
            if result is not None:
                return result

        for header, value in shared.custom_headers():
            req.setRawHeader(header, value)

        host_blocker = objreg.get('host-blocker')
        if (op == QNetworkAccessManager.GetOperation and
                host_blocker.is_blocked(req.url())):
            log.webview.info("Request to {} blocked by host blocker.".format(
                req.url().host()))
            return networkreply.ErrorNetworkReply(
                req, HOSTBLOCK_ERROR_STRING, QNetworkReply.ContentAccessDenied,
                self)

        # There are some scenarios where we can't figure out current_url:
        # - There's a generic NetworkManager, e.g. for downloads
        # - The download was in a tab which is now closed.
        current_url = QUrl()

        if self._tab_id is not None:
            try:
                tab = objreg.get('tab', scope='tab', window=self._win_id,
                                 tab=self._tab_id)
                current_url = tab.url()
            except (KeyError, RuntimeError, TypeError):
                # https://github.com/The-Compiler/qutebrowser/issues/889
                # Catching RuntimeError and TypeError because we could be in
                # the middle of the webpage shutdown here.
                current_url = QUrl()

        self.set_referer(req, current_url)

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
        reply.destroyed.connect(self._requests.remove)
        return reply
