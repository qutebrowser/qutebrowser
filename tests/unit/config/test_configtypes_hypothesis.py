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

"""Hypothesis tests for qutebrowser.config.configtypes."""

import os
import sys
import inspect
import functools

import pytest
import hypothesis
from hypothesis import strategies

from qutebrowser.config import configtypes, configexc


def gen_classes():
    for _name, member in inspect.getmembers(configtypes, inspect.isclass):
        if member is configtypes.BaseType:
            pass
        elif member is configtypes.MappingType:
            pass
        elif member is configtypes.FormatString:
            yield functools.partial(member, fields=['a', 'b'])
        elif issubclass(member, configtypes.BaseType):
            yield member


@pytest.mark.usefixtures('qapp', 'config_tmpdir')
@pytest.mark.parametrize('klass', gen_classes())
@hypothesis.given(strategies.text())
@hypothesis.example('\x00')
def test_configtypes_hypothesis(klass, s):
    if (klass in [configtypes.File, configtypes.UserStyleSheet] and
            sys.platform == 'linux' and
            not os.environ.get('DISPLAY', '')):
        pytest.skip("No DISPLAY available")

    try:
        klass().validate(s)
    except configexc.ValidationError:
        pass
    else:
        klass().transform(s)
