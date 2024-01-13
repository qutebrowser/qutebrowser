# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""End to end tests for adblocking."""

import pytest

try:
    import adblock
except ImportError:
    adblock = None

needs_adblock_lib = pytest.mark.skipif(
    adblock is None, reason="Needs 'adblock' library")


@pytest.mark.parametrize('method', [
    'auto',
    'hosts',
    pytest.param('adblock', marks=needs_adblock_lib),
    pytest.param('both', marks=needs_adblock_lib),
])
def test_adblock(method, quteproc, server):
    for kind in ['hosts', 'adblock']:
        quteproc.set_setting(
            f'content.blocking.{kind}.lists',
            f"['http://localhost:{server.port}/data/blocking/qutebrowser-{kind}']"
        )

    quteproc.set_setting('content.blocking.method', method)
    quteproc.send_cmd(':adblock-update')

    quteproc.wait_for(message="hostblock: Read 1 hosts from 1 sources.")
    if adblock is not None:
        quteproc.wait_for(
            message="braveadblock: Filters successfully read from 1 sources.")

    quteproc.open_path('data/blocking/external_logo.html')

    if method in ['hosts', 'both'] or (method == 'auto' and adblock is None):
        message = "Request to qutebrowser.org blocked by host blocker."
    else:
        message = ("Request to https://qutebrowser.org/icons/qutebrowser.svg blocked "
                   "by ad blocker.")
    quteproc.wait_for(message=message)
