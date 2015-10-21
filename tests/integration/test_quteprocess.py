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

"""Test the quteproc fixture used for tests."""

import pytest

import testprocess  # pylint: disable=import-error


def test_quteproc_error_message(qtbot, quteproc):
    """Make sure the test fails with an unexpected error message."""
    with qtbot.waitSignal(quteproc.got_error, raising=True):
        quteproc.send_cmd(':message-error test')
    # Usually we wouldn't call this from inside a test, but here we force the
    # error to occur during the test rather than at teardown time.
    with pytest.raises(pytest.fail.Exception):
        quteproc.after_test()
