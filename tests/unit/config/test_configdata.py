# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.config.configdata."""

import pytest

from qutebrowser.config import configdata


@pytest.mark.parametrize('sect', configdata.DATA.keys())
def test_section_desc(sect):
    """Make sure every section has a description."""
    desc = configdata.SECTION_DESC[sect]
    assert isinstance(desc, str)


def test_data():
    """Some simple sanity tests on data()."""
    data = configdata.data()
    assert 'general' in data
    assert 'ignore-case' in data['general']


def test_readonly_data():
    """Make sure DATA is readonly."""
    with pytest.raises(ValueError) as excinfo:
        configdata.DATA['general'].setv('temp', 'ignore-case', 'true', 'true')
    assert str(excinfo.value) == "Trying to modify a read-only config!"
