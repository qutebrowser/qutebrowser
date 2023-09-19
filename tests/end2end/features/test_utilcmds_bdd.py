# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
import pytest_bdd as bdd

bdd.scenarios('utilcmds.feature')


@pytest.fixture(autouse=True)
def turn_on_scroll_logging(quteproc):
    quteproc.turn_on_scroll_logging()
