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

import http.server
import threading
import logging
import sys
import pytest

from PyQt5.QtCore import QUrl, QT_VERSION_STR
from PyQt5.QtNetwork import (QNetworkProxy, QNetworkProxyQuery, QHostInfo,
                             QHostAddress)

from qutebrowser.browser.network import pac


pytestmark = pytest.mark.usefixtures('qapp')


def _pac_common_test(test_str):
    fun_str_f = """
        function FindProxyForURL(domain, host) {{
            {}
            return "DIRECT; PROXY 127.0.0.1:8080; SOCKS 192.168.1.1:4444";
        }}
    """

    fun_str = fun_str_f.format(test_str)
    res = pac.PACResolver(fun_str)
    proxies = res.resolve(QNetworkProxyQuery(QUrl("https://example.com/test")))
    assert len(proxies) == 3
    assert proxies[0].type() == QNetworkProxy.NoProxy
    assert proxies[1].type() == QNetworkProxy.HttpProxy
    assert proxies[1].hostName() == "127.0.0.1"
    assert proxies[1].port() == 8080
    assert proxies[2].type() == QNetworkProxy.Socks5Proxy
    assert proxies[2].hostName() == "192.168.1.1"
    assert proxies[2].port() == 4444


def _pac_equality_test(call, expected):
    test_str_f = """
        var res = ({0});
        var expected = ({1});
        if(res !== expected) {{
            throw new Error("failed test {0}: got '" + res + "', expected '" + expected + "'");
        }}
    """
    _pac_common_test(test_str_f.format(call, expected))


def _pac_except_test(caplog, call):
    test_str_f = """
        var thrown = false;
        try {{
            var res = ({0});
        }} catch(e) {{
            thrown = true;
        }}
        if(!thrown) {{
            throw new Error("failed test {0}: got '" + res + "', expected exception");
        }}
    """
    with caplog.at_level(logging.ERROR):
        _pac_common_test(test_str_f.format(call))


def _pac_noexcept_test(call):
    test_str_f = """
        var res = ({0});
    """
    _pac_common_test(test_str_f.format(call))


# pylint: disable=line-too-long, invalid-name


@pytest.mark.parametrize("domain, expected", [
    ("known.domain", "'1.2.3.4'"),
    ("bogus.domain.foobar", "null")
])
def test_dnsResolve(monkeypatch, domain, expected):
    def mock_fromName(host):
        info = QHostInfo()
        if host == "known.domain":
            info.setAddresses([QHostAddress("1.2.3.4")])
        return info
    monkeypatch.setattr(QHostInfo, 'fromName', mock_fromName)
    _pac_equality_test("dnsResolve('{}')".format(domain), expected)


def test_myIpAddress():
    _pac_equality_test("isResolvable(myIpAddress())", "true")


def test_proxyBindings():
    _pac_equality_test("JSON.stringify(ProxyConfig.bindings)", "'{}'")


def test_invalid_port():
    test_str = """
        function FindProxyForURL(domain, host) {
            return "PROXY 127.0.0.1:FOO";
        }
    """

    res = pac.PACResolver(test_str)
    with pytest.raises(pac.ParseProxyError):
        res.resolve(QNetworkProxyQuery(QUrl("https://example.com/test")))


# See https://github.com/The-Compiler/qutebrowser/pull/1891#issuecomment-259222615

try:
    from PyQt5 import QtWebEngineWidgets
except ImportError:
    QtWebEngineWidgets = None


@pytest.mark.skipif(QT_VERSION_STR.startswith('5.7') and
                    QtWebEngineWidgets is not None and
                    sys.platform == "linux",
                    reason="Segfaults when run with QtWebEngine tests on Linux")
def test_fetch():
    test_str = """
        function FindProxyForURL(domain, host) {
            return "DIRECT; PROXY 127.0.0.1:8080; SOCKS 192.168.1.1:4444";
        }
    """

    class PACHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)

            self.send_header('Content-type', 'application/x-ns-proxy-autoconfig')
            self.end_headers()

            self.wfile.write(test_str.encode("ascii"))

    ready_event = threading.Event()

    def serve():
        httpd = http.server.HTTPServer(("127.0.0.1", 8081), PACHandler)
        ready_event.set()
        httpd.handle_request()
        httpd.server_close()

    serve_thread = threading.Thread(target=serve, daemon=True)
    serve_thread.start()
    try:
        ready_event.wait()
        res = pac.PACFetcher(QUrl("pac+http://127.0.0.1:8081"))
        assert res.fetch_error() is None
    finally:
        serve_thread.join()
    proxies = res.resolve(QNetworkProxyQuery(QUrl("https://example.com/test")))
    assert len(proxies) == 3
