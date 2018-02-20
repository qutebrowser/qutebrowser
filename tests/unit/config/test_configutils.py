# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.config import configutils, configdata, configtypes
from qutebrowser.utils import urlmatch


def test_unset_object_identity():
    assert configutils._UnsetObject() is not configutils._UnsetObject()
    assert configutils.UNSET is configutils.UNSET


def test_unset_object_repr():
    assert repr(configutils.UNSET) == '<UNSET>'


@pytest.fixture
def opt():
    return configdata.Option(name='example.option', typ=configtypes.String(),
                             default='default value', backends=None,
                             raw_backends=None, description=None)

@pytest.fixture
def values(opt):
    pattern = urlmatch.UrlPattern('*://www.example.com/')
    scoped_values = [configutils.ScopedValue('global value', None),
                     configutils.ScopedValue('example value', pattern)]
    return configutils.Values(opt, scoped_values)


def test_repr(opt, values):
    expected = ("qutebrowser.config.configutils.Values(opt={!r}, "
                "values=[ScopedValue(value='global value', pattern=None), "
                "ScopedValue(value='example value', pattern=qutebrowser.utils."
                "urlmatch.UrlPattern(pattern='*://www.example.com/'))])"
                .format(opt))
    assert repr(values) == expected


def test_str_empty(opt):
    values = configutils.Values(opt)
    assert str(values) == 'example.option: <unchanged>'
