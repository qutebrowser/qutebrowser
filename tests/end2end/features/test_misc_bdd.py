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

import json

import pytest_bdd as bdd
bdd.scenarios('misc.feature')


@bdd.then(bdd.parsers.parse('the PDF {filename} should exist in the tmpdir'))
def pdf_exists(quteproc, tmpdir, filename):
    path = tmpdir / filename
    data = path.read_binary()
    assert data.startswith(b'%PDF')


@bdd.when(bdd.parsers.parse('I set up "{lists}" as block lists'))
def set_up_blocking(quteproc, lists, server):
    url = 'http://localhost:{}/data/adblock/'.format(server.port)
    urls = [url + item.strip() for item in lists.split(',')]
    quteproc.set_setting('content.host_blocking.lists', json.dumps(urls))
