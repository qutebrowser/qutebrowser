# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest_bdd as bdd
bdd.scenarios('scroll.feature')


def _get_scroll_values(quteproc):
    data = quteproc.get_session()
    pos = data['windows'][0]['tabs'][0]['history'][0]['scroll-pos']
    return (pos['x'], pos['y'])


@bdd.then(bdd.parsers.re(r"the page should be scrolled "
                         r"(?P<direction>horizontally|vertically)"))
def check_scrolled(quteproc, direction):
    x, y = _get_scroll_values(quteproc)
    if direction == 'horizontally':
        assert x != 0
        assert y == 0
    else:
        assert x == 0
        assert y != 0


@bdd.then("the page should not be scrolled")
def check_not_scrolled(quteproc):
    x, y = _get_scroll_values(quteproc)
    assert x == 0
    assert y == 0
