# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json

import pytest
import pytest_bdd as bdd


@pytest.fixture(autouse=True)
def init_fake_clipboard(quteproc):
    """Make sure the fake clipboard will be used."""
    quteproc.send_cmd(':debug-set-fake-clipboard')


@bdd.then(bdd.parsers.parse('"{text}" should be found'))
def check_found_text(request, quteproc, text):
    if request.config.webengine:
        # WORKAROUND
        # This probably should work with Qt 5.9:
        # https://codereview.qt-project.org/#/c/192920/
        # https://codereview.qt-project.org/#/c/192921/
        # https://bugreports.qt.io/browse/QTBUG-53134
        # FIXME: Doesn't actually work, investigate why.
        return
    quteproc.send_cmd(':yank selection')
    quteproc.wait_for(message='Setting fake clipboard: {}'.format(
        json.dumps(text)))


bdd.scenarios('search.feature')
