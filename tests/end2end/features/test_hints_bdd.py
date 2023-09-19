# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import textwrap

import pytest

import pytest_bdd as bdd
bdd.scenarios('hints.feature')


@pytest.fixture(autouse=True)
def set_up_word_hints(tmpdir, quteproc):
    dict_file = tmpdir / 'dict'
    dict_file.write(textwrap.dedent("""
        one
        two
        three
        four
        five
        six
        seven
        eight
        nine
        ten
        eleven
        twelve
        thirteen
    """))
    quteproc.set_setting('hints.dictionary', str(dict_file))
