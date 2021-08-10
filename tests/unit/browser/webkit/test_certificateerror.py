# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import pytest
from PyQt5.QtNetwork import QSslError

from qutebrowser.browser.webkit import certificateerror


class FakeError:

    def __init__(self, msg):
        self.msg = msg

    def errorString(self):
        return self.msg


@pytest.mark.parametrize('errors, expected', [
    (
        [QSslError(QSslError.UnableToGetIssuerCertificate)],
        ['<p>The issuer certificate could not be found</p>'],
    ),
    (
        [
            QSslError(QSslError.UnableToGetIssuerCertificate),
            QSslError(QSslError.UnableToDecryptCertificateSignature),
        ],
        [
            '<ul>',
            '<li>The issuer certificate could not be found</li>',
            '<li>The certificate signature could not be decrypted</li>',
            '</ul>',
        ],
    ),

    (
        [FakeError('Escaping test: <>')],
        ['<p>Escaping test: &lt;&gt;</p>'],
    ),
    (
        [
            FakeError('Escaping test 1: <>'),
            FakeError('Escaping test 2: <>'),
        ],
        [
            '<ul>',
            '<li>Escaping test 1: &lt;&gt;</li>',
            '<li>Escaping test 2: &lt;&gt;</li>',
            '</ul>',
        ],
    ),
])
def test_html(errors, expected):
    wrapper = certificateerror.CertificateErrorWrapper(errors)
    lines = [line.strip() for line in wrapper.html().splitlines() if line.strip()]
    assert lines == expected
