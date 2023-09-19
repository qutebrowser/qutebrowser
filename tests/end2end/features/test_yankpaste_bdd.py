# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

import pytest_bdd as bdd


bdd.scenarios('yankpaste.feature')


@pytest.fixture(autouse=True)
def init_fake_clipboard(quteproc):
    """Make sure the fake clipboard will be used."""
    quteproc.send_cmd(':debug-set-fake-clipboard')


@bdd.when(bdd.parsers.parse('I insert "{value}" into the text field'))
def set_text_field(quteproc, value):
    quteproc.send_cmd(":jseval --world=0 set_text('{}')".format(value))
    quteproc.wait_for_js('textarea set to: ' + value)
