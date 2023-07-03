# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest_bdd as bdd
bdd.scenarios('misc.feature')


@bdd.when("I load a third-party iframe")
def load_iframe(quteproc, server, ssl_server):
    quteproc.set_setting('content.tls.certificate_errors', 'load-insecurely')
    quteproc.open_path(f'https-iframe/{ssl_server.port}', port=server.port)
    msg = quteproc.wait_for(message="Certificate error: *")
    msg.expected = True
    msg = quteproc.wait_for(message="Certificate error: *")
    msg.expected = True


@bdd.then(bdd.parsers.parse('the PDF {filename} should exist in the tmpdir'))
def pdf_exists(quteproc, tmpdir, filename):
    path = tmpdir / filename
    data = path.read_binary()
    assert data.startswith(b'%PDF')
