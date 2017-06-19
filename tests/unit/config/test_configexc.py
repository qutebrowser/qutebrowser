# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2015-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.configexc."""

from qutebrowser.config import configexc
from qutebrowser.utils import usertypes


def test_validation_error():
    e = configexc.ValidationError('val', 'msg')
    assert e.section is None
    assert e.option is None
    assert str(e) == "Invalid value 'val' - msg"


def test_no_option_error():
    e = configexc.NoOptionError('opt')
    assert e.option == 'opt'
    assert str(e) == "No option 'opt'"


def test_backend_error():
    e = configexc.BackendError(usertypes.Backend.QtWebKit)
    assert str(e) == "This setting is not available with the QtWebKit backend!"


def test_duplicate_key_error():
    e = configexc.DuplicateKeyError('asdf')
    assert isinstance(e, configexc.KeybindingError)
    assert str(e) == "Duplicate key asdf"
