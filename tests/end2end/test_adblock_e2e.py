# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
