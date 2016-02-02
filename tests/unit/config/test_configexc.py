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

"""Tests for qutebrowser.config.configexc."""

from qutebrowser.config import configexc


def test_validation_error():
    e = configexc.ValidationError('val', 'msg')
    assert e.section is None
    assert e.option is None
    assert str(e) == "Invalid value 'val' - msg"


def test_no_section_error():
    e = configexc.NoSectionError('sect')
    assert e.section == 'sect'
    assert str(e) == "Section 'sect' does not exist!"


def test_no_option_error():
    e = configexc.NoOptionError('opt', 'sect')
    assert e.section == 'sect'
    assert e.option == 'opt'
    assert str(e) == "No option 'opt' in section 'sect'"


def test_interpolation_syntax_error():
    e = configexc.InterpolationSyntaxError('opt', 'sect', 'msg')
    assert e.section == 'sect'
    assert e.option == 'opt'
    assert str(e) == 'msg'
