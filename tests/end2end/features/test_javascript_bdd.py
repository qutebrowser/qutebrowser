# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
bdd.scenarios('javascript.feature')


@bdd.then("the window sizes should be the same")
def check_window_sizes(quteproc):
    hidden = quteproc.wait_for_js('hidden window size: *')
    quteproc.send_cmd(':jseval --world main updateText("visible")')
    visible = quteproc.wait_for_js('visible window size: *')
    hidden_size = hidden.message.split()[-1]
    visible_size = visible.message.split()[-1]
    assert hidden_size == visible_size
