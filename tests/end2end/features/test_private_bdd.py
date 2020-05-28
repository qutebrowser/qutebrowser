# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
bdd.scenarios('private.feature')


@bdd.then(bdd.parsers.parse('the cookie {name} should be set to {value}'))
def check_cookie(quteproc, name, value):
    """Check if a given cookie is set correctly.

    This assumes we're on the server cookies page.
    """
    content = quteproc.get_content()
    data = json.loads(content)
    print(data)
    assert data['cookies'][name] == value


@bdd.then(bdd.parsers.parse('the cookie {name} should not be set'))
def check_cookie_not_set(quteproc, name):
    """Check if a given cookie is not set."""
    content = quteproc.get_content()
    data = json.loads(content)
    print(data)
    assert name not in data['cookies']


@bdd.then(bdd.parsers.parse('the file {name} should not contain "{text}"'))
def check_not_contain(tmpdir, name, text):
    path = tmpdir / name
    assert text not in path.read()
