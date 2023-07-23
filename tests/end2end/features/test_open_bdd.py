# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

import pytest
import pytest_bdd as bdd
bdd.scenarios('open.feature')


@pytest.mark.parametrize('scheme', ['http://', ''])
def test_open_s(request, quteproc, ssl_server, scheme):
    """Test :open with -s."""
    quteproc.set_setting('content.tls.certificate_errors', 'load-insecurely')
    quteproc.send_cmd(':open -s {}localhost:{}/'
                      .format(scheme, ssl_server.port))
    if scheme == 'http://' or not request.config.webengine:
        # Error is only logged on the first error with QtWebEngine
        quteproc.mark_expected(category='message',
                               loglevel=logging.ERROR,
                               message="Certificate error: *")
    quteproc.wait_for_load_finished('/', port=ssl_server.port, https=True,
                                    load_status='warn')


def test_open_s_non_http(quteproc, ssl_server):
    """Test :open with -s and a qute:// page."""
    quteproc.send_cmd(':open -s qute://version')
    quteproc.wait_for_load_finished('qute://version')
