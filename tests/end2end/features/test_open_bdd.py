# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import logging

import pytest
import pytest_bdd as bdd
bdd.scenarios('open.feature')


@pytest.mark.parametrize('scheme', ['http://', ''])
def test_open_s(request, quteproc, ssl_server, scheme):
    """Test :open with -s."""
    quteproc.set_setting('content.ssl_strict', 'false')
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
