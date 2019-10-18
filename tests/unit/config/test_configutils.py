# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from PyQt5.QtCore import QUrl

from qutebrowser.config import configdata, configtypes, configutils
from qutebrowser.utils import urlmatch


def test_unset_object_identity():
    assert configutils.Unset() is not configutils.Unset()
    assert configutils.UNSET is configutils.UNSET


def test_unset_object_repr():
    assert repr(configutils.UNSET) == '<UNSET>'


@pytest.fixture
def opt():
    return configdata.Option(name='example.option', typ=configtypes.String(),
                             default='default value', backends=None,
                             raw_backends=None, description=None,
                             supports_pattern=True)


@pytest.fixture
def pattern():
    return urlmatch.UrlPattern('*://www.example.com/')


@pytest.fixture
def other_pattern():
    return urlmatch.UrlPattern('https://www.example.org/')


@pytest.fixture
def values(opt, pattern):
    scoped_values = [configutils.ScopedValue('global value', None),
                     configutils.ScopedValue('example value', pattern)]
    return configutils.Values(opt, scoped_values)


@pytest.fixture
def empty_values(opt):
    return configutils.Values(opt)


def test_repr(opt, values):
    expected = ("qutebrowser.config.configutils.Values(opt={!r}, "
                "values=[ScopedValue(value='global value', pattern=None), "
                "ScopedValue(value='example value', pattern=qutebrowser.utils."
                "urlmatch.UrlPattern(pattern='*://www.example.com/'))])"
                .format(opt))
    assert repr(values) == expected


def test_str(values):
    expected = [
        'example.option = global value',
        '*://www.example.com/: example.option = example value',
    ]
    assert str(values) == '\n'.join(expected)


def test_str_empty(empty_values):
    assert str(empty_values) == 'example.option: <unchanged>'


def test_bool(values, empty_values):
    assert values
    assert not empty_values


def test_iter(values):
    assert list(iter(values)) == list(iter(values._values))


def test_add_existing(values):
    values.add('new global value')
    assert values.get_for_url() == 'new global value'


def test_add_new(values, other_pattern):
    values.add('example.org value', other_pattern)
    assert values.get_for_url() == 'global value'
    example_com = QUrl('https://www.example.com/')
    example_org = QUrl('https://www.example.org/')
    assert values.get_for_url(example_com) == 'example value'
    assert values.get_for_url(example_org) == 'example.org value'


def test_remove_existing(values, pattern):
    removed = values.remove(pattern)
    assert removed

    url = QUrl('https://www.example.com/')
    assert values.get_for_url(url) == 'global value'


def test_remove_non_existing(values, other_pattern):
    removed = values.remove(other_pattern)
    assert not removed

    url = QUrl('https://www.example.com/')
    assert values.get_for_url(url) == 'example value'


def test_clear(values):
    assert values
    values.clear()
    assert not values
    assert values.get_for_url(fallback=False) is configutils.UNSET


def test_get_matching(values):
    url = QUrl('https://www.example.com/')
    assert values.get_for_url(url, fallback=False) == 'example value'


def test_get_unset(empty_values):
    assert empty_values.get_for_url(fallback=False) is configutils.UNSET


def test_get_no_global(empty_values, other_pattern):
    empty_values.add('example.org value', pattern)
    assert empty_values.get_for_url(fallback=False) is configutils.UNSET


def test_get_unset_fallback(empty_values):
    assert empty_values.get_for_url() == 'default value'


def test_get_non_matching(values):
    url = QUrl('https://www.example.ch/')
    assert values.get_for_url(url, fallback=False) is configutils.UNSET


def test_get_non_matching_fallback(values):
    url = QUrl('https://www.example.ch/')
    assert values.get_for_url(url) == 'global value'


def test_get_multiple_matches(values):
    """With multiple matching pattern, the last added should win."""
    all_pattern = urlmatch.UrlPattern('*://*/')
    values.add('new value', all_pattern)
    url = QUrl('https://www.example.com/')
    assert values.get_for_url(url) == 'new value'


def test_get_matching_pattern(values, pattern):
    assert values.get_for_pattern(pattern, fallback=False) == 'example value'


def test_get_pattern_none(values, pattern):
    assert values.get_for_pattern(None, fallback=False) == 'global value'


def test_get_unset_pattern(empty_values, pattern):
    value = empty_values.get_for_pattern(pattern, fallback=False)
    assert value is configutils.UNSET


def test_get_no_global_pattern(empty_values, pattern, other_pattern):
    empty_values.add('example.org value', other_pattern)
    value = empty_values.get_for_pattern(pattern, fallback=False)
    assert value is configutils.UNSET


def test_get_unset_fallback_pattern(empty_values, pattern):
    assert empty_values.get_for_pattern(pattern) == 'default value'


def test_get_non_matching_pattern(values, other_pattern):
    value = values.get_for_pattern(other_pattern, fallback=False)
    assert value is configutils.UNSET


def test_get_non_matching_fallback_pattern(values, other_pattern):
    assert values.get_for_pattern(other_pattern) == 'global value'


def test_get_equivalent_patterns(empty_values):
    """With multiple matching pattern, the last added should win."""
    pat1 = urlmatch.UrlPattern('https://www.example.com/')
    pat2 = urlmatch.UrlPattern('*://www.example.com/')
    empty_values.add('pat1 value', pat1)
    empty_values.add('pat2 value', pat2)

    assert empty_values.get_for_pattern(pat1) == 'pat1 value'
    assert empty_values.get_for_pattern(pat2) == 'pat2 value'
