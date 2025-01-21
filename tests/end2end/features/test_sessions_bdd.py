# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os.path
import logging

import pytest
import pytest_bdd as bdd
bdd.scenarios('sessions.feature')


@pytest.fixture(autouse=True)
def turn_on_scroll_logging(quteproc):
    quteproc.turn_on_scroll_logging()


@bdd.when(bdd.parsers.parse('I have a "{name}" session file:'))
def create_session_file(quteproc, name, docstring):
    filename = os.path.join(quteproc.basedir, 'data', 'sessions',
                            name + '.yml')
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(docstring)


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
