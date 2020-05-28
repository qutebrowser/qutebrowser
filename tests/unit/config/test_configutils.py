# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import hypothesis
from hypothesis import strategies
import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.config import configutils, configdata, configtypes, configexc
from qutebrowser.utils import urlmatch, usertypes, qtutils
from tests.helpers import utils


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
def mixed_values(opt, pattern):
    scoped_values = [configutils.ScopedValue('global value', None),
                     configutils.ScopedValue('example value', pattern,
                                             hide_userconfig=True)]
    return configutils.Values(opt, scoped_values)


@pytest.fixture
def empty_values(opt):
    return configutils.Values(opt)


def test_str(values):
    expected = [
        'example.option = global value',
        '*://www.example.com/: example.option = example value',
    ]
    assert str(values) == '\n'.join(expected)


def test_str_empty(empty_values):
    assert str(empty_values) == 'example.option: <unchanged>'


def test_str_mixed(mixed_values):
    expected = [
        'example.option = global value',
        '*://www.example.com/: example.option = example value',
    ]
    assert str(mixed_values) == '\n'.join(expected)


@pytest.mark.parametrize('include_hidden, expected', [
    (True, ['example.option = global value',
            '*://www.example.com/: example.option = example value']),
    (False, ['example.option = global value']),
])
def test_dump(mixed_values, include_hidden, expected):
    assert mixed_values.dump(include_hidden=include_hidden) == expected


def test_bool(values, empty_values):
    assert values
    assert not empty_values


def test_iter(values):
    assert list(iter(values)) == list(iter(values._vmap.values()))


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
    assert values.get_for_url(fallback=False) is usertypes.UNSET


def test_get_matching(values):
    url = QUrl('https://www.example.com/')
    assert values.get_for_url(url, fallback=False) == 'example value'


def test_get_invalid(values):
    with pytest.raises(qtutils.QtValueError):
        values.get_for_url(QUrl())


def test_get_unset(empty_values):
    assert empty_values.get_for_url(fallback=False) is usertypes.UNSET


def test_get_no_global(empty_values, other_pattern, pattern):
    empty_values.add('example.org value', pattern)
    assert empty_values.get_for_url(fallback=False) is usertypes.UNSET


def test_get_unset_fallback(empty_values):
    assert empty_values.get_for_url() == 'default value'


def test_get_non_matching(values):
    url = QUrl('https://www.example.ch/')
    assert values.get_for_url(url, fallback=False) is usertypes.UNSET


def test_get_non_matching_fallback(values):
    url = QUrl('https://www.example.ch/')
    assert values.get_for_url(url) == 'global value'


def test_get_multiple_matches(values):
    """With multiple matching pattern, the last added should win."""
    all_pattern = urlmatch.UrlPattern('*://*/')
    values.add('new value', all_pattern)
    url = QUrl('https://www.example.com/')
    assert values.get_for_url(url) == 'new value'


def test_get_non_domain_patterns(empty_values):
    """With multiple matching pattern, the last added should win."""
    pat1 = urlmatch.UrlPattern('*://*/*')
    empty_values.add('fallback')
    empty_values.add('value', pat1)

    assert empty_values.get_for_url(QUrl("http://qutebrowser.org")) == 'value'
    assert empty_values.get_for_url() == 'fallback'


def test_get_matching_pattern(values, pattern):
    assert values.get_for_pattern(pattern, fallback=False) == 'example value'


def test_get_pattern_none(values, pattern):
    assert values.get_for_pattern(None, fallback=False) == 'global value'


def test_get_unset_pattern(empty_values, pattern):
    value = empty_values.get_for_pattern(pattern, fallback=False)
    assert value is usertypes.UNSET


def test_get_no_global_pattern(empty_values, pattern, other_pattern):
    empty_values.add('example.org value', other_pattern)
    value = empty_values.get_for_pattern(pattern, fallback=False)
    assert value is usertypes.UNSET


def test_get_unset_fallback_pattern(empty_values, pattern):
    assert empty_values.get_for_pattern(pattern) == 'default value'


def test_get_non_matching_pattern(values, other_pattern):
    value = values.get_for_pattern(other_pattern, fallback=False)
    assert value is usertypes.UNSET


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


def test_get_trailing_dot(values):
    """A domain with a trailing dot should be equivalent to the same without.

    See http://www.dns-sd.org/trailingdotsindomainnames.html

    Thus, we expect to get the same setting for both.
    """
    other_pattern = urlmatch.UrlPattern('https://www.example.org./')
    values.add('example.org value', other_pattern)
    assert values.get_for_url() == 'global value'
    example_com = QUrl('https://www.example.com/')
    example_org = QUrl('https://www.example.org./')
    example_org_2 = QUrl('https://www.example.org/')
    assert values.get_for_url(example_com) == 'example value'
    assert (values.get_for_url(example_org) ==
            values.get_for_url(example_org_2) ==
            'example.org value')


@pytest.mark.parametrize('func', [
    pytest.param(lambda values, pattern:
                 values.add(None, pattern),
                 id='add'),
    pytest.param(lambda values, pattern:
                 values.remove(pattern),
                 id='remove'),
    pytest.param(lambda values, pattern:
                 values.get_for_url(QUrl('https://example.org/')),
                 id='get_for_url'),
    pytest.param(lambda values, pattern:
                 values.get_for_pattern(pattern),
                 id='get_for_pattern'),
])
def test_no_pattern_support(func, opt, pattern):
    opt.supports_pattern = False
    values = configutils.Values(opt, [])

    with pytest.raises(configexc.NoPatternError):
        func(values, pattern)


def test_add_url_benchmark(values, benchmark):
    blocked_hosts = list(utils.blocked_hosts())

    def _add_blocked():
        for line in blocked_hosts:
            values.add(False, urlmatch.UrlPattern(line))

    benchmark(_add_blocked)


@pytest.mark.parametrize('url', [
    'http://www.qutebrowser.com/',
    'http://foo.bar.baz/',
    'http://bop.foo.bar.baz/',
])
def test_domain_lookup_sparse_benchmark(url, values, benchmark):
    url = QUrl(url)
    values.add(False, urlmatch.UrlPattern("*.foo.bar.baz"))
    for line in utils.blocked_hosts():
        values.add(False, urlmatch.UrlPattern(line))

    benchmark(lambda: values.get_for_url(url))


class TestWiden:

    @pytest.mark.parametrize('hostname, expected', [
        ('a.b.c', ['a.b.c', 'b.c', 'c']),
        ('foobarbaz', ['foobarbaz']),
        ('', []),
        ('.c', ['.c', 'c']),
        ('c.', ['c.']),
        ('.c.', ['.c.', 'c.']),
        (None, []),
    ])
    def test_widen_hostnames(self, hostname, expected):
        assert list(configutils._widened_hostnames(hostname)) == expected

    @pytest.mark.parametrize('hostname', [
        'test.qutebrowser.org',
        'a.b.c.d.e.f.g.h.i.j.k.l.m.n.o.p.q.r.s.t.u.v.w.z.y.z',
        'qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq.c',
    ])
    def test_bench_widen_hostnames(self, hostname, benchmark):
        benchmark(lambda: list(configutils._widened_hostnames(hostname)))


class TestFontFamilies:

    @pytest.mark.parametrize('family_str, expected', [
        ('foo, bar', ['foo', 'bar']),
        ('foo,   spaces ', ['foo', 'spaces']),
        ('', []),
        ('foo, ', ['foo']),
        ('"One Font", Two', ['One Font', 'Two']),
        ("One, 'Two Fonts'", ['One', 'Two Fonts']),
        ("One, 'Two Fonts', 'Three'", ['One', 'Two Fonts', 'Three']),
        ("\"Weird font name: '\"", ["Weird font name: '"]),
    ])
    def test_from_str(self, family_str, expected):
        assert list(configutils.FontFamilies.from_str(family_str)) == expected

    @pytest.mark.parametrize('families, quote, expected', [
        (['family'], True, 'family'),
        (['family1', 'family2'], True, 'family1, family2'),
        (['family'], True, 'family'),
        (['space family', 'alien'], True, '"space family", alien'),
        (['comma,family', 'period'], True, '"comma,family", period'),

        (['family'], False, 'family'),
        (['family1', 'family2'], False, 'family1, family2'),
        (['family'], False, 'family'),
        (['space family', 'alien'], False, 'space family, alien'),
        (['comma,family', 'period'], False, 'comma,family, period'),
    ])
    def test_to_str(self, families, quote, expected):
        ff = configutils.FontFamilies(families)
        assert ff.to_str(quote=quote) == expected
        if quote:
            assert str(ff) == expected

    @hypothesis.given(strategies.text())
    def test_from_str_hypothesis(self, family_str):
        families = configutils.FontFamilies.from_str(family_str)

        for family in families:
            assert family

        str(families)
