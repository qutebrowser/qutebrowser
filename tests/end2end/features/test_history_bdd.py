# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import re

import pytest
import pytest_bdd as bdd

bdd.scenarios('history.feature')


@pytest.fixture(autouse=True)
def turn_on_sql_history(quteproc):
    """Make sure SQL writing is enabled for tests in this module."""
    cmd = ":debug-pyeval objects.debug_flags.remove('no-sql-history')"
    quteproc.send_cmd(cmd)
    quteproc.wait_for_load_finished_url('qute://pyeval')
    quteproc.wait_for(message='INSERT INTO History *', category='sql')


@bdd.then(bdd.parsers.parse("the query parameter {name} should be set to "
                            "{value}"))
def check_query(quteproc, name, value):
    """Check if a given query is set correctly.

    This assumes we're on the server query page.
    """
    content = quteproc.get_content()
    data = json.loads(content)
    print(data)
    assert data[name] == value


@bdd.then(bdd.parsers.parse("the history should contain:\n{expected}"))
def check_history(quteproc, server, tmpdir, expected):
    quteproc.wait_for(message='INSERT INTO History *', category='sql')
    path = tmpdir / 'history'
    quteproc.send_cmd(':debug-dump-history "{}"'.format(path))
    quteproc.wait_for(category='message', loglevel=logging.INFO,
                      message='Dumped history to {}'.format(path))

    with path.open('r', encoding='utf-8') as f:
        # ignore access times, they will differ in each run
        actual = '\n'.join(re.sub('^\\d+-?', '', line).strip() for line in f)

    expected = expected.replace('(port)', str(server.port))
    assert actual == expected


@bdd.then("the history should be empty")
def check_history_empty(quteproc, server, tmpdir):
    quteproc.wait_for(message='DELETE FROM History', category='sql')
    check_history(quteproc, server, tmpdir, '')
