# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.utils.javascript."""

import dataclasses

import pytest
import hypothesis
import hypothesis.strategies

from qutebrowser.utils import javascript, usertypes


@dataclasses.dataclass
class Case:

    original: str
    replacement: str
    webkit_only: bool = False

    def __str__(self):
        return self.original


class TestStringEscape:

    TESTS = [
        Case('foo\\bar', r'foo\\bar'),
        Case('foo\nbar', r'foo\nbar'),
        Case('foo\rbar', r'foo\rbar'),
        Case("foo'bar", r"foo\'bar"),
        Case('foo"bar', r'foo\"bar'),
        Case('one\\two\rthree\nfour\'five"six', r'one\\two\rthree\nfour\'five\"six'),
        Case('\x00', r'\x00', webkit_only=True),
        Case('hellö', 'hellö'),
        Case('☃', '☃'),
        Case('\x80Ā', '\x80Ā'),
        Case('𐀀\x00𐀀\x00', r'𐀀\x00𐀀\x00', webkit_only=True),
        Case('𐀀\ufeff', r'𐀀\ufeff'),
        Case('\ufeff', r'\ufeff', webkit_only=True),
        # https://stackoverflow.com/questions/2965293/
        Case('\u2028', r'\u2028'),
        Case('\u2029', r'\u2029'),
    ]

    # Once there was this warning here:
    #   load glyph failed err=6 face=0x2680ba0, glyph=1912
    # Should that be ignored?

    @pytest.mark.parametrize('case', TESTS, ids=str)
    def test_fake_escape(self, case):
        """Test javascript escaping with some expected outcomes."""
        assert javascript.string_escape(case.original) == case.replacement

    def _test_escape(self, text, web_tab, qtbot):
        """Test conversion by running JS in a tab."""
        escaped = javascript.string_escape(text)

        with qtbot.wait_callback() as cb:
            web_tab.run_js_async('"{}";'.format(escaped), cb)

        cb.assert_called_with(text)

    @pytest.mark.parametrize('case', TESTS, ids=str)
    def test_real_escape(self, web_tab, qtbot, case):
        """Test javascript escaping with a real QWebPage."""
        if web_tab.backend == usertypes.Backend.QtWebEngine and case.webkit_only:
            pytest.xfail("Not supported with QtWebEngine")
        self._test_escape(case.original, web_tab, qtbot)

    @pytest.mark.qt_log_ignore('^OpenType support missing for script')
    @hypothesis.given(hypothesis.strategies.text())
    def test_real_escape_hypothesis(self, web_tab, qtbot, text):
        """Test javascript escaping with a real QWebPage and hypothesis."""
        if web_tab.backend == usertypes.Backend.QtWebEngine:
            hypothesis.assume('\x00' not in text)
        self._test_escape(text, web_tab, qtbot)


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
