# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Evaluation of PAC scripts."""

import sys
import functools

from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot)
from PyQt5.QtNetwork import (QNetworkProxy, QNetworkRequest, QHostInfo,
                             QNetworkReply, QNetworkAccessManager,
                             QHostAddress)
from PyQt5.QtQml import QJSEngine, QJSValue

from qutebrowser.utils import log, utils, qtutils


class ParseProxyError(Exception):

    """Error while parsing PAC result string."""

    pass


class EvalProxyError(Exception):

    """Error while evaluating PAC script."""

    pass


def _js_slot(*args):
    """Wrap a methods as a JavaScript function.

    Register a PACContext method as a JavaScript function, and catch
    exceptions returning them as JavaScript Error objects.

    Args:
        args: Types of method arguments.

    Return: Wrapped method.
    """
    def _decorator(method):
        @functools.wraps(method)
        def new_method(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except:
                e = str(sys.exc_info()[0])
                log.network.exception("PAC evaluation error")
                # pylint: disable=protected-access
                return self._error_con.callAsConstructor([e])
                # pylint: enable=protected-access
        return pyqtSlot(*args, result=QJSValue)(new_method)
    return _decorator


class _PACContext(QObject):

    """Implementation of PAC API functions that require native calls.

    See https://developer.mozilla.org/en-US/docs/Mozilla/Projects/Necko/Proxy_Auto-Configuration_(PAC)_file
    """

    JS_DEFINITIONS = """
        function dnsResolve(host) {
            return PAC.dnsResolve(host);
        }

        function myIpAddress() {
            return PAC.myIpAddress();
        }
    """

    def __init__(self, engine):
        """Create a new PAC API implementation instance.

        Args:
            engine: QJSEngine which is used for running PAC.
        """
        super().__init__(parent=engine)
        self._engine = engine
        self._error_con = engine.globalObject().property("Error")

    @_js_slot(str)
    def dnsResolve(self, host):
        """Resolve a DNS hostname.

        Resolves the given DNS hostname into an IP address, and returns it
        in the dot-separated format as a string.

        Args:
            host: hostname to resolve.
        """
        ips = QHostInfo.fromName(host)
        if ips.error() != QHostInfo.NoError or not ips.addresses():
            err_f = "Failed to resolve host during PAC evaluation: {}"
            log.network.info(err_f.format(host))
            return QJSValue(QJSValue.NullValue)
        else:
            return ips.addresses()[0].toString()

    @_js_slot()
    def myIpAddress(self):
        """Get host IP address.

        Return the server IP address of the current machine, as a string in
        the dot-separated integer format.
        """
        return QHostAddress(QHostAddress.LocalHost).toString()


class PACResolver(object):

    """Evaluate PAC script files and resolve proxies."""

    @staticmethod
    def _parse_proxy_host(host_str):
        host, _colon, port_str = host_str.partition(':')
        try:
            port = int(port_str)
        except ValueError:
            raise ParseProxyError("Invalid port number")
        return (host, port)

    @staticmethod
    def _parse_proxy_entry(proxy_str):
        """Parse one proxy string entry, as described in PAC specification."""
        config = [c.strip() for c in proxy_str.split(' ') if c]
        if not config:
            raise ParseProxyError("Empty proxy entry")
        elif config[0] == "DIRECT":
            if len(config) != 1:
                raise ParseProxyError("Invalid number of parameters for " +
                                      "DIRECT")
            return QNetworkProxy(QNetworkProxy.NoProxy)
        elif config[0] == "PROXY":
            if len(config) != 2:
                raise ParseProxyError("Invalid number of parameters for PROXY")
            host, port = PACResolver._parse_proxy_host(config[1])
            return QNetworkProxy(QNetworkProxy.HttpProxy, host, port)
        elif config[0] == "SOCKS":
            if len(config) != 2:
                raise ParseProxyError("Invalid number of parameters for SOCKS")
            host, port = PACResolver._parse_proxy_host(config[1])
            return QNetworkProxy(QNetworkProxy.Socks5Proxy, host, port)
        else:
            err = "Unknown proxy type: {}"
            raise ParseProxyError(err.format(config[0]))

    @staticmethod
    def _parse_proxy_string(proxy_str):
        proxies = proxy_str.split(';')
        return [PACResolver._parse_proxy_entry(x) for x in proxies]

    def _evaluate(self, js_code, js_file):
        ret = self._engine.evaluate(js_code, js_file)
        if ret.isError():
            err = "JavaScript error while evaluating PAC file: {}"
            raise EvalProxyError(err.format(ret.toString()))

    def __init__(self, pac_str):
        """Create a PAC resolver.

        Args:
            pac_str: JavaScript code containing PAC resolver.
        """
        self._engine = QJSEngine()

        self._ctx = _PACContext(self._engine)
        self._engine.globalObject().setProperty(
            "PAC", self._engine.newQObject(self._ctx))
        self._evaluate(_PACContext.JS_DEFINITIONS, "pac_js_definitions")
        self._evaluate(utils.read_file("javascript/pac_utils.js"), "pac_utils")
        proxy_config = self._engine.newObject()
        proxy_config.setProperty("bindings", self._engine.newObject())
        self._engine.globalObject().setProperty("ProxyConfig", proxy_config)

        self._evaluate(pac_str, "pac")
        global_js_object = self._engine.globalObject()
        self._resolver = global_js_object.property("FindProxyForURL")
        if not self._resolver.isCallable():
            err = "Cannot resolve FindProxyForURL function, got '{}' instead"
            raise EvalProxyError(err.format(self._resolver.toString()))

    def resolve(self, query):
        """Resolve a proxy via PAC.

        Args:
            query: QNetworkProxyQuery.

        Return:
            A list of QNetworkProxy objects in order of preference.
        """
        result = self._resolver.call([query.url().toString(),
                                      query.peerHostName()])
        result_str = result.toString()
        if not result.isString():
            err = "Got strange value from FindProxyForURL: '{}'"
            raise EvalProxyError(err.format(result_str))
        return self._parse_proxy_string(result_str)


class PACFetcher(QObject):

    """Asynchronous fetcher of PAC files."""

    finished = pyqtSignal()

    def __init__(self, url, parent=None):
        """Resolve a PAC proxy from URL.

        Args:
            url: QUrl of a PAC proxy.
        """
        super().__init__(parent)

        pac_prefix = "pac+"

        assert url.scheme().startswith(pac_prefix)
        url.setScheme(url.scheme()[len(pac_prefix):])

        self._manager = QNetworkAccessManager()
        self._manager.setProxy(QNetworkProxy(QNetworkProxy.NoProxy))
        self._reply = self._manager.get(QNetworkRequest(url))
        self._reply.finished.connect(self._finish)
        self._pac = None
        self._error_message = None

    @pyqtSlot()
    def _finish(self):
        if self._reply.error() != QNetworkReply.NoError:
            error = "Can't fetch PAC file from URL, error code {}: {}"
            self._error_message = error.format(
                self._reply.error(), self._reply.errorString())
            log.network.error(self._error_message)
        else:
            try:
                pacscript = bytes(self._reply.readAll()).decode("utf-8")
            except UnicodeError as e:
                error = "Invalid encoding of a PAC file: {}"
                self._error_message = error.format(e)
                log.network.exception(self._error_message)
            try:
                self._pac = PACResolver(pacscript)
                log.network.debug("Successfully evaluated PAC file.")
            except EvalProxyError as e:
                error = "Error in PAC evaluation: {}"
                self._error_message = error.format(e)
                log.network.exception(self._error_message)
        self._manager = None
        self._reply = None
        self.finished.emit()

    def _wait(self):
        """Wait until a reply from the remote server is received."""
        if self._manager is not None:
            loop = qtutils.EventLoop()
            self.finished.connect(loop.quit)
            loop.exec_()

    def fetch_error(self):
        """Check if PAC script is successfully fetched.

        Return None iff PAC script is downloaded and evaluated successfully,
        error string otherwise.
        """
        self._wait()
        return self._error_message

    def resolve(self, query):
        """Resolve a query via PAC.

        Args: QNetworkProxyQuery.

        Return a list of QNetworkProxy objects in order of preference.
        """
        self._wait()
        try:
            return self._pac.resolve(query)
        except (EvalProxyError, ParseProxyError) as e:
            log.network.exception("Error in PAC resolution: {}.".format(e))
            # .invalid is guaranteed to be inaccessible in RFC 6761.
            # Port 9 is for DISCARD protocol -- DISCARD servers act like
            # /dev/null.
            # Later NetworkManager.createRequest will detect this and display
            # an error message.
            error_host = "pac-resolve-error.qutebrowser.invalid"
            return QNetworkProxy(QNetworkProxy.HttpProxy, error_host, 9)
