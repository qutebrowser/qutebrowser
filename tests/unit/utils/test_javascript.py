# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import binascii
import os.path

import pytest
import hypothesis
import hypothesis.strategies
from PyQt5.QtCore import PYQT_VERSION

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

    def _test_escape(self, text, qtbot, webframe):
        """Helper function for test_real_escape*."""
        try:
            self._test_escape_simple(text, webframe)
        except AssertionError:
            # Try another method if the simple method failed.
            #
            # See _test_escape_hexlified documentation on why this is
            # necessary.
            self._test_escape_hexlified(text, qtbot, webframe)

    def _test_escape_hexlified(self, text, qtbot, webframe):
        """Test conversion by hexlifying in javascript.

        Since the conversion of QStrings to Python strings is broken in some
        older PyQt versions in some corner cases, we load an HTML file which
        generates an MD5 of the escaped text and use that for comparisons.
        """
        escaped = javascript.string_escape(text)
        path = os.path.join(os.path.dirname(__file__),
                            'test_javascript_string_escape.html')
        with open(path, encoding='utf-8') as f:
            html_source = f.read().replace('%INPUT%', escaped)

        with qtbot.waitSignal(webframe.loadFinished) as blocker:
            webframe.setHtml(html_source)
        assert blocker.args == [True]

        result = webframe.evaluateJavaScript('window.qute_test_result')
        assert result is not None
        assert '|' in result
        result_md5, result_text = result.split('|', maxsplit=1)
        text_md5 = binascii.hexlify(text.encode('utf-8')).decode('ascii')
        assert result_md5 == text_md5, result_text

    def _test_escape_simple(self, text, webframe):
        """Test conversion by using evaluateJavaScript."""
        escaped = javascript.string_escape(text)
        result = webframe.evaluateJavaScript('"{}";'.format(escaped))
        assert result == text

    @pytest.mark.parametrize('text', sorted(TESTS), ids=repr)
    def test_real_escape(self, webframe, qtbot, text):
        """Test javascript escaping with a real QWebPage."""
        self._test_escape(text, qtbot, webframe)

    @pytest.mark.qt_log_ignore('^OpenType support missing for script')
    @hypothesis.given(hypothesis.strategies.text())
    def test_real_escape_hypothesis(self, webframe, qtbot, text):
        """Test javascript escaping with a real QWebPage and hypothesis."""
        # We can't simply use self._test_escape because of this:
        # https://github.com/pytest-dev/pytest-qt/issues/69

        # self._test_escape(text, qtbot, webframe)
        try:
            self._test_escape_simple(text, webframe)
        except AssertionError:
            if PYQT_VERSION >= 0x050300:
                self._test_escape_hexlified(text, qtbot, webframe)


@pytest.mark.parametrize('arg, expected', [
    ('foobar', '"foobar"'),
    ('foo\\bar', r'"foo\\bar"'),
    (42, '42'),
    (23.42, '23.42'),
    (None, 'undefined'),
    (object(), TypeError),
])
def test_convert_js_arg(arg, expected):
    if expected is TypeError:
        with pytest.raises(TypeError):
            javascript._convert_js_arg(arg)
    else:
        assert javascript._convert_js_arg(arg) == expected


def test_assemble():
    expected = '"use strict";\nwindow._qutebrowser.foo.func(23);'
    assert javascript.assemble('foo', 'func', 23) == expected
