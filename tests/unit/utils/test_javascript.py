# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.javascript."""

import pytest
import hypothesis
import hypothesis.strategies

from qutebrowser.utils import javascript


class TestStringEscape:

    TESTS = {
        'foo\\bar': r'foo\\bar',
        'foo\nbar': r'foo\nbar',
        'foo\rbar': r'foo\rbar',
        "foo'bar": r"foo\'bar",
        'foo"bar': r'foo\"bar',
        'one\\two\rthree\nfour\'five"six': r'one\\two\rthree\nfour\'five\"six',
        '\x00': r'\x00',
        'hellö': 'hellö',
        '☃': '☃',
        '\x80Ā': '\x80Ā',
        '𐀀\x00𐀀\x00': r'𐀀\x00𐀀\x00',
        '𐀀\ufeff': r'𐀀\ufeff',
        '\ufeff': r'\ufeff',
        # http://stackoverflow.com/questions/2965293/
        '\u2028': r'\u2028',
        '\u2029': r'\u2029',
    }

    # Once there was this warning here:
    #   load glyph failed err=6 face=0x2680ba0, glyph=1912
    # http://qutebrowser.org:8010/builders/debian-jessie/builds/765/steps/unittests/
    # Should that be ignored?

    @pytest.mark.parametrize('before, after', sorted(TESTS.items()), ids=repr)
    def test_fake_escape(self, before, after):
        """Test javascript escaping with some expected outcomes."""
        assert javascript.string_escape(before) == after

    def _test_escape(self, text, webframe):
        """Test conversion by using evaluateJavaScript."""
        escaped = javascript.string_escape(text)
        result = webframe.evaluateJavaScript('"{}";'.format(escaped))
        assert result == text

    @pytest.mark.parametrize('text', sorted(TESTS), ids=repr)
    def test_real_escape(self, webframe, text):
        """Test javascript escaping with a real QWebPage."""
        self._test_escape(text, webframe)

    @pytest.mark.qt_log_ignore('^OpenType support missing for script')
    @hypothesis.given(hypothesis.strategies.text())
    def test_real_escape_hypothesis(self, webframe, text):
        """Test javascript escaping with a real QWebPage and hypothesis."""
        self._test_escape(text, webframe)


@pytest.mark.parametrize('arg, expected', [
    ('foobar', '"foobar"'),
    ('foo\\bar', r'"foo\\bar"'),
    (42, '42'),
    (23.42, '23.42'),
    (False, 'false'),
    (None, 'undefined'),
    (object(), TypeError),
    (True, 'true'),
    ([23, True, 'x'], '[23, true, "x"]'),
])
def test_to_js(arg, expected):
    if expected is TypeError:
        with pytest.raises(TypeError):
            javascript.to_js(arg)
    else:
        assert javascript.to_js(arg) == expected


@pytest.mark.parametrize('base, expected_base', [
    ('window', 'window'),
    ('foo', 'window._qutebrowser.foo'),
])
def test_assemble(base, expected_base):
    expected = '"use strict";\n{}.func(23);'.format(expected_base)
    assert javascript.assemble(base, 'func', 23) == expected


def test_wrap_global():
    source = javascript.wrap_global('name',
                                    'console.log("foo");',
                                    'console.log("bar");')
    assert 'window._qutebrowser.initialized["name"]' in source
    assert 'console.log("foo");' in source
    assert 'console.log("bar");' in source
