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

"""Our own QNetworkAccessManager."""

import collections
import html
import typing

import attr
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, QCoreApplication, QUrl,
                          QByteArray)
from PyQt5.QtNetwork import (QNetworkAccessManager, QNetworkReply, QSslSocket,
                             QSslError)

from qutebrowser.config import config
from qutebrowser.utils import (message, log, usertypes, utils, objreg,
                               urlutils, debug)
from qutebrowser.browser import shared
from qutebrowser.browser.network import proxy as proxymod
from qutebrowser.extensions import interceptors
from qutebrowser.browser.webkit import certificateerror, cookies, cache
from qutebrowser.browser.webkit.network import (webkitqutescheme, networkreply,
                                                filescheme)
from qutebrowser.misc import objects

if typing.TYPE_CHECKING:
    from qutebrowser.mainwindow import prompt


HOSTBLOCK_ERROR_STRING = '%HOSTBLOCK%'
_proxy_auth_cache = {}  # type: typing.Dict[ProxyId, prompt.AuthInfo]


@attr.s(frozen=True)
class ProxyId:

    """Information identifying a proxy server."""

    type = attr.ib()
    hostname = attr.ib()
    port = attr.ib()


def _is_secure_cipher(cipher):
    """Check if a given SSL cipher (hopefully) isn't broken yet."""
    tokens = [e.upper() for e in cipher.name().split('-')]
    if cipher.usedBits() < 128:
        # https://codereview.qt-project.org/#/c/75943/
        return False
    # OpenSSL should already protect against this in a better way
    elif cipher.keyExchangeMethod() == 'DH' and utils.is_windows:
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
    default_ciphers = QSslSocket.defaultCiphers()
    log.init.debug("Default Qt ciphers: {}".format(
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


_SavedErrorsType = typing.MutableMapping[urlutils.HostTupleType,
                                         typing.Sequence[QSslError]]


class NetworkManager(QNetworkAccessManager):

    """Our own QNetworkAccessManager.

    Attributes:
        adopted_downloads: If downloads are running with this QNAM but the
                           associated tab gets closed already, the NAM gets
                           reparented to the DownloadManager. This counts the
                           still running downloads, so the QNAM can clean
                           itself up when this reaches zero again.
        _scheme_handlers: A dictionary (scheme -> handler) of supported custom
                          schemes.
        _win_id: The window ID this NetworkManager is associated with.
                 (or None for generic network managers)
        _tab_id: The tab ID this NetworkManager is associated with.
                 (or None for generic network managers)
        _rejected_ssl_errors: A {QUrl: [SslError]} dict of rejected errors.
        _accepted_ssl_errors: A {QUrl: [SslError]} dict of accepted errors.
        _private: Whether we're in private browsing mode.
        netrc_used: Whether netrc authentication was performed.

    Signals:
        shutting_down: Emitted when the QNAM is shutting down.
    """

    shutting_down = pyqtSignal()

    def __init__(self, *, win_id, tab_id, private, parent=None):
        log.init.debug("Initializing NetworkManager")
        with log.disable_qt_msghandler():
            # WORKAROUND for a hang when a message is printed - See:
            # http://www.riverbankcomputing.com/pipermail/pyqt/2014-November/035045.html
            super().__init__(parent)
        log.init.debug("NetworkManager init done")
        self.adopted_downloads = 0
        self._win_id = win_id
        self._tab_id = tab_id
        self._private = private
        self._scheme_handlers = {
            'qute': webkitqutescheme.handler,
            'file': filescheme.handler,
        }
        self._set_cookiejar()
        self._set_cache()
        self.sslErrors.connect(  # type: ignore[attr-defined]
            self.on_ssl_errors)
        self._rejected_ssl_errors = collections.defaultdict(
            list)  # type: _SavedErrorsType
        self._accepted_ssl_errors = collections.defaultdict(
            list)  # type: _SavedErrorsType
        self.authenticationRequired.connect(  # type: ignore[attr-defined]
            self.on_authentication_required)
        self.proxyAuthenticationRequired.connect(  # type: ignore[attr-defined]
            self.on_proxy_authentication_required)
        self.netrc_used = False

    def _set_cookiejar(self):
        """Set the cookie jar of the NetworkManager correctly."""
        if self._private:
            cookie_jar = cookies.ram_cookie_jar
        else:
            cookie_jar = cookies.cookie_jar
        assert cookie_jar is not None

        # We have a shared cookie jar - we restore its parent so we don't
        # take ownership of it.
        self.setCookieJar(cookie_jar)
        app = QCoreApplication.instance()
        cookie_jar.setParent(app)

    def _set_cache(self):
        """Set the cache of the NetworkManager correctly."""
        if self._private:
            return
        # We have a shared cache - we restore its parent so we don't take
        # ownership of it.
        app = QCoreApplication.instance()
        self.setCache(cache.diskcache)
        cache.diskcache.setParent(app)

    def _get_abort_signals(self, owner=None):
        """Get a list of signals which should abort a question."""
        abort_on = [self.shutting_down]
        if owner is not None:
            abort_on.append(owner.destroyed)
        # This might be a generic network manager, e.g. one belonging to a
        # DownloadManager. In this case, just skip the webview thing.
        if self._tab_id is not None:
            assert self._win_id is not None
            tab = objreg.get('tab', scope='tab', window=self._win_id,
                             tab=self._tab_id)
            abort_on.append(tab.load_started)
        return abort_on

    def shutdown(self):
        """Abort all running requests."""
        self.setNetworkAccessible(QNetworkAccessManager.NotAccessible)
        self.shutting_down.emit()

    # No @pyqtSlot here, see
    # https://github.com/qutebrowser/qutebrowser/issues/2213
    def on_ssl_errors(self, reply, errors):  # noqa: C901 pragma: no mccabe
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
            host_tpl = urlutils.host_tuple(
                reply.url())  # type: typing.Optional[urlutils.HostTupleType]
        except ValueError:
            host_tpl = None
            is_accepted = False
            is_rejected = False
        else:
            assert host_tpl is not None
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
        url = reply.url()
        log.network.debug("Authentication requested for {}, netrc_used {}"
                          .format(url.toDisplayString(), self.netrc_used))

        netrc_success = False
        if not self.netrc_used:
            self.netrc_used = True
            netrc_success = shared.netrc_authentication(url, authenticator)

        if not netrc_success:
            log.network.debug("Asking for credentials")
            abort_on = self._get_abort_signals(reply)
            shared.authentication_required(url, authenticator,
                                           abort_on=abort_on)

    @pyqtSlot('QNetworkProxy', 'QAuthenticator*')
    def on_proxy_authentication_required(self, proxy, authenticator):
        """Called when a proxy needs authentication."""
        proxy_id = ProxyId(proxy.type(), proxy.hostName(), proxy.port())
        if proxy_id in _proxy_auth_cache:
            authinfo = _proxy_auth_cache[proxy_id]
            authenticator.setUser(authinfo.user)
            authenticator.setPassword(authinfo.password)
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
        referer_header_conf = config.val.content.headers.referer

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

        Args:
             op: Operation op
             req: const QNetworkRequest & req
             outgoing_data: QIODevice * outgoingData

        Return:
            A QNetworkReply.
        """
        if proxymod.application_factory is not None:
            proxy_error = proxymod.application_factory.get_error()
            if proxy_error is not None:
                return networkreply.ErrorNetworkReply(
                    req, proxy_error, QNetworkReply.UnknownProxyError,
                    self)

        for header, value in shared.custom_headers(url=req.url()):
            req.setRawHeader(header, value)

        # There are some scenarios where we can't figure out current_url:
        # - There's a generic NetworkManager, e.g. for downloads
        # - The download was in a tab which is now closed.
        current_url = QUrl()

        if self._tab_id is not None:
            assert self._win_id is not None
            try:
                tab = objreg.get('tab', scope='tab', window=self._win_id,
                                 tab=self._tab_id)
                current_url = tab.url()
            except (KeyError, RuntimeError):
                # https://github.com/qutebrowser/qutebrowser/issues/889
                # Catching RuntimeError because we could be in the middle of
                # the webpage shutdown here.
                current_url = QUrl()

        request = interceptors.Request(first_party_url=current_url,
                                       request_url=req.url())
        interceptors.run(request)
        if request.is_blocked:
            return networkreply.ErrorNetworkReply(
                req, HOSTBLOCK_ERROR_STRING, QNetworkReply.ContentAccessDenied,
                self)

        if 'log-requests' in objects.debug_flags:
            operation = debug.qenum_key(QNetworkAccessManager, op)
            operation = operation.replace('Operation', '').upper()
            log.webview.debug("{} {}, first-party {}".format(
                operation,
                req.url().toDisplayString(),
                current_url.toDisplayString()))

        scheme = req.url().scheme()
        if scheme in self._scheme_handlers:
            result = self._scheme_handlers[scheme](req, op, current_url)
            if result is not None:
                result.setParent(self)
                return result

        self.set_referer(req, current_url)
        return super().createRequest(op, req, outgoing_data)
