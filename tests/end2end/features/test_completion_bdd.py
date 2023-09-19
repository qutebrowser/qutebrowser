# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest_bdd as bdd
bdd.scenarios('completion.feature')


@bdd.then(bdd.parsers.parse("the completion model should be {model}"))
def check_model(quteproc, model):
    """Make sure the completion model was set to something."""
    pattern = "Starting {} completion *".format(model)
    quteproc.wait_for(message=pattern)
