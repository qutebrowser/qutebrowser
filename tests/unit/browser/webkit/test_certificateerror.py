# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from qutebrowser.qt.core import QUrl
from qutebrowser.qt.network import QSslError

from qutebrowser.browser.webkit import certificateerror


class FakeError:

    def __init__(self, msg):
        self.msg = msg

    def errorString(self):
        return self.msg


@pytest.mark.parametrize('error_factories, expected', [
    (
        [lambda: QSslError(QSslError.SslError.UnableToGetIssuerCertificate)],
        ['<p>The issuer certificate could not be found</p>'],
    ),
    (
        [
            lambda: QSslError(QSslError.SslError.UnableToGetIssuerCertificate),
            lambda: QSslError(QSslError.SslError.UnableToDecryptCertificateSignature),
        ],
        [
            '<ul>',
            '<li>The issuer certificate could not be found</li>',
            '<li>The certificate signature could not be decrypted</li>',
            '</ul>',
        ],
    ),

    (
        [lambda: FakeError('Escaping test: <>')],
        ['<p>Escaping test: &lt;&gt;</p>'],
    ),
    (
        [
            lambda: FakeError('Escaping test 1: <>'),
            lambda: FakeError('Escaping test 2: <>'),
        ],
        [
            '<ul>',
            '<li>Escaping test 1: &lt;&gt;</li>',
            '<li>Escaping test 2: &lt;&gt;</li>',
            '</ul>',
        ],
    ),
])
def test_html(stubs, error_factories, expected):
    reply = stubs.FakeNetworkReply(url=QUrl("https://example.com"))
    errors = [factory() for factory in error_factories]
    wrapper = certificateerror.CertificateErrorWrapper(reply=reply, errors=errors)
    lines = [line.strip() for line in wrapper.html().splitlines() if line.strip()]
    assert lines == expected
