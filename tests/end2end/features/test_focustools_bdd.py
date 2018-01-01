# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Jay Kamat <jaygkamat@gmail.com>
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

import pytest
import logging

import pytest_bdd as bdd
bdd.scenarios('focustools.feature')


@bdd.then(bdd.parsers.parse("no element should be focused"))
def check_not_focused(quteproc):
    """Make sure the completion model was set to something."""
    quteproc.send_cmd(':jseval document.activeElement == document.body',
                      escape=False)
    message = quteproc.wait_for(loglevel=logging.INFO, category='message',
                                message='*')
    assert message.message == "True"


@bdd.then(bdd.parsers.parse("an element should be focused"))
def check_focused(quteproc):
    """Make sure the completion model was set to something."""
    quteproc.send_cmd(':jseval document.activeElement == document.body',
                      escape=False)
    message = quteproc.wait_for(loglevel=logging.INFO, category='message',
                                message='*')
    assert message.message == "False"
