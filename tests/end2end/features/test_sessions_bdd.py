# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os.path
import logging

import pytest
import pytest_bdd as bdd
bdd.scenarios('sessions.feature')


@pytest.fixture(autouse=True)
def turn_on_scroll_logging(quteproc):
    quteproc.turn_on_scroll_logging()


@bdd.when(bdd.parsers.parse('I have a "{name}" session file:\n{contents}'))
def create_session_file(quteproc, name, contents):
    filename = os.path.join(quteproc.basedir, 'data', 'sessions',
                            name + '.yml')
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(contents)


@bdd.when(bdd.parsers.parse('I replace "{pattern}" by "{replacement}" in the '
                            '"{name}" session file'))
def session_replace(quteproc, server, pattern, replacement, name):
    # First wait until the session was actually saved
    quteproc.wait_for(category='message', loglevel=logging.INFO,
                      message='Saved session {}.'.format(name))
    filename = os.path.join(quteproc.basedir, 'data', 'sessions',
                            name + '.yml')
    replacement = replacement.replace('(port)', str(server.port))  # yo dawg
    with open(filename, 'r', encoding='utf-8') as f:
        data = f.read()
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(data.replace(pattern, replacement))


@bdd.then(bdd.parsers.parse("the session {name} should exist"))
def session_should_exist(quteproc, name):
    filename = os.path.join(quteproc.basedir, 'data', 'sessions',
                            name + '.yml')
    assert os.path.exists(filename)


@bdd.then(bdd.parsers.parse("the session {name} should not exist"))
def session_should_not_exist(quteproc, name):
    filename = os.path.join(quteproc.basedir, 'data', 'sessions',
                            name + '.yml')
    assert not os.path.exists(filename)
