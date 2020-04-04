# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import pytest

from PyQt5.QtCore import QUrl
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


@pytest.mark.parametrize("host, expected", [
    ("example", "true"),
    ("example.com", "false"),
    ("www.example.com", "false"),
])
def test_isPlainHostName(host, expected):
    _pac_equality_test("isPlainHostName('{}')".format(host), expected)


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


@pytest.mark.parametrize('string', ["", "{"])
def test_wrong_pac_string(string):
    with pytest.raises(pac.EvalProxyError):
        pac.PACResolver(string)


@pytest.mark.parametrize("value", [
    "",
    "DIRECT FOO",
    "PROXY",
    "SOCKS",
    "FOOBAR",
])
def test_fail_parse(value):
    test_str_f = """
        function FindProxyForURL(domain, host) {{
            return "{}";
        }}
    """

    res = pac.PACResolver(test_str_f.format(value))
    with pytest.raises(pac.ParseProxyError):
        res.resolve(QNetworkProxyQuery(QUrl("https://example.com/test")))


def test_fail_return():
    test_str = """
        function FindProxyForURL(domain, host) {
            return null;
        }
    """

    res = pac.PACResolver(test_str)
    with pytest.raises(pac.EvalProxyError):
        res.resolve(QNetworkProxyQuery(QUrl("https://example.com/test")))


@pytest.mark.parametrize('url, has_secret', [
    ('http://example.com/secret', True),  # path passed with HTTP
    ('http://example.com?secret=yes', True),  # query passed with HTTP
    ('http://secret@example.com', False),  # user stripped with HTTP
    ('http://user:secret@example.com', False),  # password stripped with HTTP

    ('https://example.com/secret', False),  # path stripped with HTTPS
    ('https://example.com?secret=yes', False),  # query stripped with HTTPS
    ('https://secret@example.com', False),  # user stripped with HTTPS
    ('https://user:secret@example.com', False),  # password stripped with HTTPS
])
@pytest.mark.parametrize('from_file', [True, False])
def test_secret_url(url, has_secret, from_file):
    """Make sure secret parts in a URL are stripped correctly.

    The following parts are considered secret:
        - If the PAC info is loaded from a local file, nothing.
        - If the URL to resolve is a HTTP URL, the username/password.
        - If the URL to resolve is a HTTPS URL, the username/password, query
          and path.
    """
    test_str = """
        function FindProxyForURL(domain, host) {{
            has_secret = domain.indexOf("secret") !== -1;
            expected_secret = {};
            if (has_secret !== expected_secret) {{
                throw new Error("Expected secret: " + expected_secret + ", found: " + has_secret + " in " + domain);
            }}
            return "DIRECT";
        }}
    """.format('true' if (has_secret or from_file) else 'false')
    res = pac.PACResolver(test_str)
    res.resolve(QNetworkProxyQuery(QUrl(url)), from_file=from_file)


def test_logging(qtlog):
    """Make sure console.log() works for PAC files."""
    test_str = """
        function FindProxyForURL(domain, host) {
            console.log("logging test");
            return "DIRECT";
        }
    """
    res = pac.PACResolver(test_str)
    res.resolve(QNetworkProxyQuery(QUrl("https://example.com/test")))
    assert len(qtlog.records) == 1
    assert qtlog.records[0].message == 'logging test'


def fetcher_test(test_str):
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
        fetcher = pac.PACFetcher(QUrl("pac+http://127.0.0.1:8081"))
        fetcher.fetch()
        assert fetcher.fetch_error() is None
    finally:
        serve_thread.join()
    return fetcher


def test_fetch_success():
    test_str = """
        function FindProxyForURL(domain, host) {
            return "DIRECT; PROXY 127.0.0.1:8080; SOCKS 192.168.1.1:4444";
        }
    """

    res = fetcher_test(test_str)
    proxies = res.resolve(QNetworkProxyQuery(QUrl("https://example.com/test")))
    assert len(proxies) == 3


def test_fetch_evalerror(caplog):
    test_str = """
        function FindProxyForURL(domain, host) {
            return "FOO";
        }
    """

    res = fetcher_test(test_str)
    with caplog.at_level(logging.ERROR):
        proxies = res.resolve(QNetworkProxyQuery(QUrl("https://example.com/test")))
    assert len(proxies) == 1
    assert proxies[0].port() == 9
