# SPDX-FileCopyrightText: Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

import pytest_bdd as bdd
bdd.scenarios('marks.feature')


@pytest.fixture(autouse=True)
def turn_on_scroll_logging(quteproc):
    quteproc.turn_on_scroll_logging(no_scroll_filtering=True)


@bdd.then(bdd.parsers.parse("the page should be scrolled to {x} {y}"))
def check_y(request, quteproc, x, y):
    data = quteproc.get_session()
    pos = data['windows'][0]['tabs'][0]['history'][-1]['scroll-pos']
    assert int(x) == pos['x']
    assert int(y) == pos['y']
