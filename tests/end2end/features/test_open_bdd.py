# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest_bdd as bdd
bdd.scenarios('open.feature')


def test_open_s(quteproc, ssl_server):
    """Test :open with -s."""
    quteproc.set_setting('content.ssl_strict', 'false')
    quteproc.send_cmd(':open -s http://localhost:{}/'.format(ssl_server.port))
    quteproc.mark_expected(category='message',
                           loglevel=logging.ERROR,
                           message="Certificate error: *")
    quteproc.wait_for_load_finished('/', port=ssl_server.port, https=True,
                                    load_status='warn')
