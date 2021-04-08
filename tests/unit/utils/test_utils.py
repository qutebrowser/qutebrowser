# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.utils.utils."""

import sys
import enum
import os
import io
import logging
import functools
import re
import shlex
import math
import operator

from PyQt5.QtCore import QUrl, QRect
from PyQt5.QtGui import QClipboard
import pytest
import hypothesis
from hypothesis import strategies
import yaml

import qutebrowser
import qutebrowser.utils  # for test_qualname
from qutebrowser.utils import utils, usertypes
from qutebrowser.utils.utils import VersionNumber


class TestVersionNumber:

    @pytest.mark.parametrize('num, expected', [
        (VersionNumber(5, 15, 2), 'VersionNumber(5, 15, 2)'),
        (VersionNumber(5, 15), 'VersionNumber(5, 15)'),
        (VersionNumber(5), 'VersionNumber(5)'),
    ])
    def test_repr(self, num, expected):
        assert repr(num) == expected

    @pytest.mark.parametrize('num, expected', [
        (VersionNumber(5, 15, 2), '5.15.2'),
        (VersionNumber(5, 15), '5.15'),
        (VersionNumber(5), '5'),
        (VersionNumber(1, 2, 3, 4), '1.2.3.4'),
    ])
    def test_str(self, num, expected):
        assert str(num) == expected

    def test_not_normalized(self):
        with pytest.raises(ValueError, match='Refusing to construct'):
            VersionNumber(5, 15, 0)

    @pytest.mark.parametrize('num, expected', [
        (VersionNumber(5, 15, 2), VersionNumber(5, 15)),
        (VersionNumber(5, 15), VersionNumber(5, 15)),
        (VersionNumber(6), VersionNumber(6)),
        (VersionNumber(1, 2, 3, 4), VersionNumber(1, 2)),
    ])
    def test_strip_patch(self, num, expected):
        assert num.strip_patch() == expected

    @pytest.mark.parametrize('s, expected', [
        ('1x6.2', VersionNumber(1)),
        ('6', VersionNumber(6)),
        ('5.15', VersionNumber(5, 15)),
        ('5.15.3', VersionNumber(5, 15, 3)),
        ('5.15.3.dev1234', VersionNumber(5, 15, 3)),
        ('1.2.3.4', VersionNumber(1, 2, 3, 4)),
    ])
    def test_parse_valid(self, s, expected):
        assert VersionNumber.parse(s) == expected

    @pytest.mark.parametrize('s, message', [
        ('foo6', "Failed to parse foo6"),
        ('.6', "Failed to parse .6"),
        ('0x6.2', "Can't construct a null version"),
    ])
    def test_parse_invalid(self, s, message):
        with pytest.raises(ValueError, match=message):
            VersionNumber.parse(s)

    @pytest.mark.parametrize('lhs, op, rhs, outcome', [
        # ==
        (VersionNumber(6), operator.eq, VersionNumber(6), True),
        (VersionNumber(6), operator.eq, object(), False),

        # !=
        (VersionNumber(6), operator.ne, VersionNumber(5), True),
        (VersionNumber(6), operator.ne, object(), True),

        # >=
        (VersionNumber(5, 14), operator.ge, VersionNumber(5, 13, 5), True),
        (VersionNumber(5, 14), operator.ge, VersionNumber(5, 14, 2), False),
        (VersionNumber(5, 14, 3), operator.ge, VersionNumber(5, 14, 2), True),
        (VersionNumber(5, 14, 3), operator.ge, VersionNumber(5, 14, 3), True),
        (VersionNumber(5, 14), operator.ge, VersionNumber(5, 13), True),
        (VersionNumber(5, 14), operator.ge, VersionNumber(5, 14), True),
        (VersionNumber(5, 14), operator.ge, VersionNumber(5, 15), False),
        (VersionNumber(5, 14), operator.ge, VersionNumber(4), True),
        (VersionNumber(5, 14), operator.ge, VersionNumber(5), True),
        (VersionNumber(5, 14), operator.ge, VersionNumber(6), False),

        # >
        (VersionNumber(5, 14), operator.gt, VersionNumber(5, 13, 5), True),
        (VersionNumber(5, 14), operator.gt, VersionNumber(5, 14, 2), False),
        (VersionNumber(5, 14, 3), operator.gt, VersionNumber(5, 14, 2), True),
        (VersionNumber(5, 14, 3), operator.gt, VersionNumber(5, 14, 3), False),
        (VersionNumber(5, 14), operator.gt, VersionNumber(5, 13), True),
        (VersionNumber(5, 14), operator.gt, VersionNumber(5, 14), False),
        (VersionNumber(5, 14), operator.gt, VersionNumber(5, 15), False),
        (VersionNumber(5, 14), operator.gt, VersionNumber(4), True),
        (VersionNumber(5, 14), operator.gt, VersionNumber(5), True),
        (VersionNumber(5, 14), operator.gt, VersionNumber(6), False),

        # <=
        (VersionNumber(5, 14), operator.le, VersionNumber(5, 13, 5), False),
        (VersionNumber(5, 14), operator.le, VersionNumber(5, 14, 2), True),
        (VersionNumber(5, 14, 3), operator.le, VersionNumber(5, 14, 2), False),
        (VersionNumber(5, 14, 3), operator.le, VersionNumber(5, 14, 3), True),
        (VersionNumber(5, 14), operator.le, VersionNumber(5, 13), False),
        (VersionNumber(5, 14), operator.le, VersionNumber(5, 14), True),
        (VersionNumber(5, 14), operator.le, VersionNumber(5, 15), True),
        (VersionNumber(5, 14), operator.le, VersionNumber(4), False),
        (VersionNumber(5, 14), operator.le, VersionNumber(5), False),
        (VersionNumber(5, 14), operator.le, VersionNumber(6), True),

        # <
        (VersionNumber(5, 14), operator.lt, VersionNumber(5, 13, 5), False),
        (VersionNumber(5, 14), operator.lt, VersionNumber(5, 14, 2), True),
        (VersionNumber(5, 14, 3), operator.lt, VersionNumber(5, 14, 2), False),
        (VersionNumber(5, 14, 3), operator.lt, VersionNumber(5, 14, 3), False),
        (VersionNumber(5, 14), operator.lt, VersionNumber(5, 13), False),
        (VersionNumber(5, 14), operator.lt, VersionNumber(5, 14), False),
        (VersionNumber(5, 14), operator.lt, VersionNumber(5, 15), True),
        (VersionNumber(5, 14), operator.lt, VersionNumber(4), False),
        (VersionNumber(5, 14), operator.lt, VersionNumber(5), False),
        (VersionNumber(5, 14), operator.lt, VersionNumber(6), True),
    ])
    def test_comparisons(self, lhs, op, rhs, outcome):
        assert op(lhs, rhs) == outcome


ELLIPSIS = '\u2026'


class TestCompactText:

    """Test compact_text."""

    @pytest.mark.parametrize('text, expected', [
        ('foo\nbar', 'foobar'),
        ('  foo  \n  bar  ', 'foobar'),
        ('\nfoo\n', 'foo'),
    ], ids=repr)
    def test_compact_text(self, text, expected):
        """Test folding of newlines."""
        assert utils.compact_text(text) == expected

    @pytest.mark.parametrize('elidelength, text, expected', [
        (None, 'x' * 100, 'x' * 100),
        (6, 'foobar', 'foobar'),
        (5, 'foobar', 'foob' + ELLIPSIS),
        (5, 'foo\nbar', 'foob' + ELLIPSIS),
        (7, 'foo\nbar', 'foobar'),
    ], ids=lambda val: repr(val)[:20])
    def test_eliding(self, elidelength, text, expected):
        """Test eliding."""
        assert utils.compact_text(text, elidelength) == expected


class TestEliding:

    """Test elide."""

    def test_too_small(self):
        """Test eliding to 0 chars which should fail."""
        with pytest.raises(ValueError):
            utils.elide('foo', 0)

    @pytest.mark.parametrize('text, length, expected', [
        ('foo', 1, ELLIPSIS),
        ('foo', 3, 'foo'),
        ('foobar', 3, 'fo' + ELLIPSIS),
    ])
    def test_elided(self, text, length, expected):
        assert utils.elide(text, length) == expected


class TestElidingFilenames:

    """Test elide_filename."""

    def test_too_small(self):
        """Test eliding to less than 3 characters which should fail."""
        with pytest.raises(ValueError):
            utils.elide_filename('foo', 1)

    @pytest.mark.parametrize('filename, length, expected', [
        ('foobar', 3, '...'),
        ('foobar.txt', 50, 'foobar.txt'),
        ('foobarbazqux.py', 10, 'foo...x.py'),
    ])
    def test_elided(self, filename, length, expected):
        assert utils.elide_filename(filename, length) == expected


@pytest.mark.parametrize('seconds, out', [
    (-1, '-0:01'),
    (0, '0:00'),
    (59, '0:59'),
    (60, '1:00'),
    (60.4, '1:00'),
    (61, '1:01'),
    (-61, '-1:01'),
    (3599, '59:59'),
    (3600, '1:00:00'),
    (3601, '1:00:01'),
    (36000, '10:00:00'),
])
def test_format_seconds(seconds, out):
    assert utils.format_seconds(seconds) == out


class TestFormatSize:

    """Tests for format_size.

    Class attributes:
        TESTS: A list of (input, output) tuples.
    """

    TESTS = [
        (-1024, '-1.00k'),
        (-1, '-1.00'),
        (0, '0.00'),
        (1023, '1023.00'),
        (1024, '1.00k'),
        (1034.24, '1.01k'),
        (1024 * 1024 * 2, '2.00M'),
        (1024 ** 10, '1024.00Y'),
        (None, '?.??'),
    ]

    KILO_TESTS = [(999, '999.00'), (1000, '1.00k'), (1010, '1.01k')]

    @pytest.mark.parametrize('size, out', TESTS)
    def test_format_size(self, size, out):
        """Test format_size with several tests."""
        assert utils.format_size(size) == out

    @pytest.mark.parametrize('size, out', TESTS)
    def test_suffix(self, size, out):
        """Test the suffix option."""
        assert utils.format_size(size, suffix='B') == out + 'B'

    @pytest.mark.parametrize('size, out', KILO_TESTS)
    def test_base(self, size, out):
        """Test with an alternative base."""
        assert utils.format_size(size, base=1000) == out


class TestFakeIOStream:

    """Test FakeIOStream."""

    def _write_func(self, text):
        return text

    def test_flush(self):
        """Smoke-test to see if flushing works."""
        s = utils.FakeIOStream(self._write_func)
        s.flush()

    def test_isatty(self):
        """Make sure isatty() is always false."""
        s = utils.FakeIOStream(self._write_func)
        assert not s.isatty()

    def test_write(self):
        """Make sure writing works."""
        s = utils.FakeIOStream(self._write_func)
        assert s.write('echo') == 'echo'


class TestFakeIO:

    """Test FakeIO."""

    @pytest.fixture(autouse=True)
    def restore_streams(self):
        """Restore sys.stderr/sys.stdout after tests."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        yield
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    def test_normal(self, capsys):
        """Test without changing sys.stderr/sys.stdout."""
        data = io.StringIO()
        with utils.fake_io(data.write):
            sys.stdout.write('hello\n')
            sys.stderr.write('world\n')

        out, err = capsys.readouterr()
        assert not out
        assert not err
        assert data.getvalue() == 'hello\nworld\n'

        sys.stdout.write('back to\n')
        sys.stderr.write('normal\n')
        out, err = capsys.readouterr()
        assert out == 'back to\n'
        assert err == 'normal\n'

    def test_stdout_replaced(self, capsys):
        """Test with replaced stdout."""
        data = io.StringIO()
        new_stdout = io.StringIO()
        with utils.fake_io(data.write):
            sys.stdout.write('hello\n')
            sys.stderr.write('world\n')
            sys.stdout = new_stdout

        out, err = capsys.readouterr()
        assert not out
        assert not err
        assert data.getvalue() == 'hello\nworld\n'

        sys.stdout.write('still new\n')
        sys.stderr.write('normal\n')
        out, err = capsys.readouterr()
        assert not out
        assert err == 'normal\n'
        assert new_stdout.getvalue() == 'still new\n'

    def test_stderr_replaced(self, capsys):
        """Test with replaced stderr."""
        data = io.StringIO()
        new_stderr = io.StringIO()
        with utils.fake_io(data.write):
            sys.stdout.write('hello\n')
            sys.stderr.write('world\n')
            sys.stderr = new_stderr

        out, err = capsys.readouterr()
        assert not out
        assert not err
        assert data.getvalue() == 'hello\nworld\n'

        sys.stdout.write('normal\n')
        sys.stderr.write('still new\n')
        out, err = capsys.readouterr()
        assert out == 'normal\n'
        assert not err
        assert new_stderr.getvalue() == 'still new\n'


class GotException(Exception):

    """Exception used for TestDisabledExcepthook."""


def excepthook(_exc, _val, _tb):
    pass


def excepthook_2(_exc, _val, _tb):
    pass


class TestDisabledExcepthook:

    """Test disabled_excepthook.

    This doesn't test much as some things are untestable without triggering
    the excepthook (which is hard to test).
    """

    @pytest.fixture(autouse=True)
    def restore_excepthook(self):
        """Restore sys.excepthook and sys.__excepthook__ after tests."""
        old_excepthook = sys.excepthook
        old_dunder_excepthook = sys.__excepthook__
        yield
        sys.excepthook = old_excepthook
        sys.__excepthook__ = old_dunder_excepthook

    def test_normal(self):
        """Test without changing sys.excepthook."""
        sys.excepthook = excepthook
        assert sys.excepthook is excepthook
        with utils.disabled_excepthook():
            assert sys.excepthook is not excepthook
        assert sys.excepthook is excepthook

    def test_changed(self):
        """Test with changed sys.excepthook."""
        sys.excepthook = excepthook
        with utils.disabled_excepthook():
            assert sys.excepthook is not excepthook
            sys.excepthook = excepthook_2
        assert sys.excepthook is excepthook_2


class TestPreventExceptions:

    """Test prevent_exceptions."""

    @utils.prevent_exceptions(42)
    def func_raising(self):
        raise Exception

    def test_raising(self, caplog):
        """Test with a raising function."""
        with caplog.at_level(logging.ERROR, 'misc'):
            ret = self.func_raising()
        assert ret == 42
        expected = 'Error in test_utils.TestPreventExceptions.func_raising'
        assert caplog.messages == [expected]

    @utils.prevent_exceptions(42)
    def func_not_raising(self):
        return 23

    def test_not_raising(self, caplog):
        """Test with a non-raising function."""
        with caplog.at_level(logging.ERROR, 'misc'):
            ret = self.func_not_raising()
        assert ret == 23
        assert not caplog.records

    @utils.prevent_exceptions(42, True)
    def func_predicate_true(self):
        raise Exception

    def test_predicate_true(self, caplog):
        """Test with a True predicate."""
        with caplog.at_level(logging.ERROR, 'misc'):
            ret = self.func_predicate_true()
        assert ret == 42
        assert len(caplog.records) == 1

    @utils.prevent_exceptions(42, False)
    def func_predicate_false(self):
        raise Exception

    def test_predicate_false(self, caplog):
        """Test with a False predicate."""
        with caplog.at_level(logging.ERROR, 'misc'):
            with pytest.raises(Exception):
                self.func_predicate_false()
        assert not caplog.records


class Obj:

    """Test object for test_get_repr()."""


@pytest.mark.parametrize('constructor, attrs, expected', [
    (False, {}, '<test_utils.Obj>'),
    (False, {'foo': None}, '<test_utils.Obj foo=None>'),
    (False, {'foo': "b'ar", 'baz': 2}, '<test_utils.Obj baz=2 foo="b\'ar">'),
    (True, {}, 'test_utils.Obj()'),
    (True, {'foo': None}, 'test_utils.Obj(foo=None)'),
    (True, {'foo': "te'st", 'bar': 2}, 'test_utils.Obj(bar=2, foo="te\'st")'),
])
def test_get_repr(constructor, attrs, expected):
    """Test get_repr()."""
    assert utils.get_repr(Obj(), constructor, **attrs) == expected


class QualnameObj():

    """Test object for test_qualname."""

    def func(self):
        """Test method for test_qualname."""


def qualname_func(_blah):
    """Test function for test_qualname."""


QUALNAME_OBJ = QualnameObj()


@pytest.mark.parametrize('obj, expected', [
    pytest.param(QUALNAME_OBJ, repr(QUALNAME_OBJ), id='instance'),
    pytest.param(QualnameObj, 'test_utils.QualnameObj', id='class'),
    pytest.param(QualnameObj.func, 'test_utils.QualnameObj.func',
                 id='unbound-method'),
    pytest.param(QualnameObj().func, 'test_utils.QualnameObj.func',
                 id='bound-method'),
    pytest.param(qualname_func, 'test_utils.qualname_func', id='function'),
    pytest.param(functools.partial(qualname_func, True),
                 'test_utils.qualname_func', id='partial'),
    pytest.param(qutebrowser, 'qutebrowser', id='module'),
    pytest.param(qutebrowser.utils, 'qutebrowser.utils', id='submodule'),
    pytest.param(utils, 'qutebrowser.utils.utils', id='from-import'),
])
def test_qualname(obj, expected):
    assert utils.qualname(obj) == expected


class TestIsEnum:

    """Test is_enum."""

    def test_enum(self):
        """Test is_enum with an enum."""
        class Foo(enum.Enum):

            bar = enum.auto()
            baz = enum.auto()

        assert utils.is_enum(Foo)

    def test_class(self):
        """Test is_enum with a non-enum class."""
        class Test:

            """Test class for is_enum."""

        assert not utils.is_enum(Test)

    def test_object(self):
        """Test is_enum with a non-enum object."""
        assert not utils.is_enum(23)


class SomeEnum(enum.Enum):

    some_value = enum.auto()


class TestPyEnumStr:

    @pytest.fixture
    def val(self):
        return SomeEnum.some_value

    def test_fake_old_python_version(self, monkeypatch, val):
        monkeypatch.setattr(sys, 'version_info', (3, 9, 2))
        assert utils.pyenum_str(val) == str(val)

    def test_fake_new_python_version(self, monkeypatch, val):
        monkeypatch.setattr(sys, 'version_info', (3, 10, 0))
        assert utils.pyenum_str(val) == repr(val)

    def test_real_result(self, val):
        assert utils.pyenum_str(val) == 'SomeEnum.some_value'

    @pytest.mark.skipif(sys.version_info[:2] < (3, 10), reason='Needs Python 3.10+')
    def test_needed(self, val):
        """Fail if this change gets revered before the final 3.10 release."""
        assert str(val) != 'SomeEnum.some_value'


class TestRaises:

    """Test raises."""

    def do_raise(self):
        """Helper function which raises an exception."""
        raise Exception

    def do_nothing(self):
        """Helper function which does nothing."""

    @pytest.mark.parametrize('exception, value, expected', [
        (ValueError, 'a', True),
        ((ValueError, TypeError), 'a', True),
        ((ValueError, TypeError), None, True),

        (ValueError, '1', False),
        ((ValueError, TypeError), 1, False),
    ])
    def test_raises_int(self, exception, value, expected):
        """Test raises with a single exception which gets raised."""
        assert utils.raises(exception, int, value) == expected

    def test_no_args_true(self):
        """Test with no args and an exception which gets raised."""
        assert utils.raises(Exception, self.do_raise)

    def test_no_args_false(self):
        """Test with no args and an exception which does not get raised."""
        assert not utils.raises(Exception, self.do_nothing)

    def test_unrelated_exception(self):
        """Test with an unrelated exception."""
        with pytest.raises(Exception):
            utils.raises(ValueError, self.do_raise)


@pytest.mark.parametrize('inp, enc, expected', [
    ('hello world', 'ascii', 'hello world'),
    ('hellö wörld', 'utf-8', 'hellö wörld'),
    ('hellö wörld', 'ascii', 'hell? w?rld'),
])
def test_force_encoding(inp, enc, expected):
    assert utils.force_encoding(inp, enc) == expected


class TestSanitizeFilename:

    LONG_FILENAME = ("this is a very long filename which is probably longer "
                     "than 255 bytes if I continue typing some more nonsense "
                     "I will find out that a lot of nonsense actually fits in "
                     "those 255 bytes still not finished wow okay only about "
                     "50 to go and 30 now finally enough.txt")

    LONG_EXTENSION = (LONG_FILENAME.replace("filename", ".extension")
                      .replace(".txt", ""))

    @pytest.mark.parametrize('inp, expected', [
        pytest.param('normal.txt', 'normal.txt',
                     marks=pytest.mark.fake_os('windows')),
        pytest.param('user/repo issues.mht', 'user_repo issues.mht',
                     marks=pytest.mark.fake_os('windows')),
        pytest.param('<Test\\File> - "*?:|', '_Test_File_ - _____',
                     marks=pytest.mark.fake_os('windows')),
        pytest.param('<Test\\File> - "*?:|', '<Test\\File> - "*?_|',
                     marks=pytest.mark.fake_os('mac')),
        pytest.param('<Test\\File> - "*?:|', '<Test\\File> - "*?:|',
                     marks=pytest.mark.fake_os('posix')),
        (LONG_FILENAME, LONG_FILENAME),  # no shortening
    ])
    def test_special_chars(self, inp, expected):
        assert utils.sanitize_filename(inp) == expected

    @pytest.mark.parametrize('inp, expected', [
        (
            LONG_FILENAME,
            LONG_FILENAME.replace("now finally enough.txt", "n.txt")
        ),
        (
            LONG_EXTENSION,
            LONG_EXTENSION.replace("this is a very long .extension",
                                   "this .extension"),
        ),
    ])
    @pytest.mark.linux
    def test_shorten(self, inp, expected):
        assert utils.sanitize_filename(inp, shorten=True) == expected

    @pytest.mark.fake_os('windows')
    def test_empty_replacement(self):
        name = '/<Bad File>/'
        assert utils.sanitize_filename(name, replacement=None) == 'Bad File'

    @hypothesis.given(filename=strategies.text(min_size=100))
    def test_invariants(self, filename):
        sanitized = utils.sanitize_filename(filename, shorten=True)
        assert len(os.fsencode(sanitized)) <= 255 - len("(123).download")


class TestGetSetClipboard:

    @pytest.fixture(autouse=True)
    def clipboard_mock(self, mocker):
        m = mocker.patch('qutebrowser.utils.utils.QApplication.clipboard',
                         autospec=True)
        clipboard = m()
        clipboard.text.return_value = 'mocked clipboard text'
        mocker.patch('qutebrowser.utils.utils.fake_clipboard', None)
        return clipboard

    def test_set(self, clipboard_mock, caplog):
        utils.set_clipboard('Hello World')
        clipboard_mock.setText.assert_called_with('Hello World',
                                                  mode=QClipboard.Clipboard)
        assert not caplog.records

    def test_set_unsupported_selection(self, clipboard_mock):
        clipboard_mock.supportsSelection.return_value = False
        with pytest.raises(utils.SelectionUnsupportedError):
            utils.set_clipboard('foo', selection=True)

    @pytest.mark.parametrize('selection, what, text, expected', [
        (True, 'primary selection', 'fake text', 'fake text'),
        (False, 'clipboard', 'fake text', 'fake text'),
        (False, 'clipboard', 'füb', r'f\u00fcb'),
    ])
    def test_set_logging(self, clipboard_mock, caplog, selection, what,
                         text, expected):
        utils.log_clipboard = True
        utils.set_clipboard(text, selection=selection)
        assert not clipboard_mock.setText.called
        expected = 'Setting fake {}: "{}"'.format(what, expected)
        assert caplog.messages[0] == expected

    def test_get(self):
        assert utils.get_clipboard() == 'mocked clipboard text'

    @pytest.mark.parametrize('selection', [True, False])
    def test_get_empty(self, clipboard_mock, selection):
        clipboard_mock.text.return_value = ''
        with pytest.raises(utils.ClipboardEmptyError):
            utils.get_clipboard(selection=selection)

    def test_get_unsupported_selection(self, clipboard_mock):
        clipboard_mock.supportsSelection.return_value = False
        with pytest.raises(utils.SelectionUnsupportedError):
            utils.get_clipboard(selection=True)

    def test_get_unsupported_selection_fallback(self, clipboard_mock):
        clipboard_mock.supportsSelection.return_value = False
        clipboard_mock.text.return_value = 'text'
        assert utils.get_clipboard(selection=True, fallback=True) == 'text'

    @pytest.mark.parametrize('selection', [True, False])
    def test_get_fake_clipboard(self, selection):
        utils.fake_clipboard = 'fake clipboard text'
        utils.get_clipboard(selection=selection)
        assert utils.fake_clipboard is None

    @pytest.mark.parametrize('selection', [True, False])
    def test_supports_selection(self, clipboard_mock, selection):
        clipboard_mock.supportsSelection.return_value = selection
        assert utils.supports_selection() == selection

    def test_fallback_without_selection(self):
        with pytest.raises(ValueError):
            utils.get_clipboard(fallback=True)


class TestOpenFile:

    @pytest.mark.not_frozen
    @pytest.mark.not_flatpak
    def test_cmdline_without_argument(self, caplog, config_stub):
        executable = shlex.quote(sys.executable)
        cmdline = '{} -c pass'.format(executable)
        utils.open_file('/foo/bar', cmdline)
        result = caplog.messages[0]
        assert re.fullmatch(
            r'Opening /foo/bar with \[.*python.*/foo/bar.*\]', result)

    @pytest.mark.not_frozen
    @pytest.mark.not_flatpak
    def test_cmdline_with_argument(self, caplog, config_stub):
        executable = shlex.quote(sys.executable)
        cmdline = '{} -c pass {{}} raboof'.format(executable)
        utils.open_file('/foo/bar', cmdline)
        result = caplog.messages[0]
        assert re.fullmatch(
            r"Opening /foo/bar with \[.*python.*/foo/bar.*'raboof'\]", result)

    @pytest.mark.not_frozen
    @pytest.mark.not_flatpak
    def test_setting_override(self, caplog, config_stub):
        executable = shlex.quote(sys.executable)
        cmdline = '{} -c pass'.format(executable)
        config_stub.val.downloads.open_dispatcher = cmdline
        utils.open_file('/foo/bar')
        result = caplog.messages[1]
        assert re.fullmatch(
            r"Opening /foo/bar with \[.*python.*/foo/bar.*\]", result)

    @pytest.fixture
    def openurl_mock(self, mocker):
        return mocker.patch('PyQt5.QtGui.QDesktopServices.openUrl', spec={},
                            new_callable=mocker.Mock)

    def test_system_default_application(self, caplog, config_stub,
                                        openurl_mock):
        utils.open_file('/foo/bar')
        result = caplog.messages[0]
        assert re.fullmatch(
            r"Opening /foo/bar with the system application", result)
        openurl_mock.assert_called_with(QUrl('file:///foo/bar'))

    def test_cmdline_sandboxed(self, fake_flatpak,
                               config_stub, message_mock, caplog):
        with caplog.at_level(logging.ERROR):
            utils.open_file('/foo/bar', 'custom_cmd')
        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text == 'Cannot spawn download dispatcher from sandbox'

    @pytest.mark.not_frozen
    def test_setting_override_sandboxed(self, fake_flatpak, openurl_mock,
                                        caplog, config_stub):
        config_stub.val.downloads.open_dispatcher = 'test'

        with caplog.at_level(logging.WARNING):
            utils.open_file('/foo/bar')

        assert caplog.messages[1] == ('Ignoring download dispatcher from '
                                      'config in sandbox environment')
        openurl_mock.assert_called_with(QUrl('file:///foo/bar'))

    def test_system_default_sandboxed(self, config_stub, openurl_mock,
                                      fake_flatpak):
        utils.open_file('/foo/bar')
        openurl_mock.assert_called_with(QUrl('file:///foo/bar'))


def test_unused():
    utils.unused(None)


@pytest.mark.parametrize('path, expected', [
    ('E:', 'E:\\'),
    ('e:', 'e:\\'),
    ('E:foo', 'E:foo'),
    ('E:\\', 'E:\\'),
    ('E:\\foo', 'E:\\foo'),
    ('foo:', 'foo:'),
    ('foo:bar', 'foo:bar'),
])
def test_expand_windows_drive(path, expected):
    assert utils.expand_windows_drive(path) == expected


class TestYaml:

    def test_load(self):
        assert utils.yaml_load("[1, 2]") == [1, 2]

    def test_load_float_bug(self):
        with pytest.raises(yaml.YAMLError):
            utils.yaml_load("._")

    def test_load_file(self, tmp_path):
        tmpfile = tmp_path / 'foo.yml'
        tmpfile.write_text('[1, 2]')
        with tmpfile.open(encoding='utf-8') as f:
            assert utils.yaml_load(f) == [1, 2]

    def test_dump(self):
        assert utils.yaml_dump([1, 2]) == '- 1\n- 2\n'

    def test_dump_file(self, tmp_path):
        tmpfile = tmp_path / 'foo.yml'
        tmpfile.write_text(utils.yaml_dump([1, 2]), encoding='utf-8')
        assert tmpfile.read_text() == '- 1\n- 2\n'


@pytest.mark.parametrize('elems, n, expected', [
    ([], 1, []),
    ([1], 1, [[1]]),
    ([1, 2], 2, [[1, 2]]),
    ([1, 2, 3, 4], 2, [[1, 2], [3, 4]]),
])
def test_chunk(elems, n, expected):
    assert list(utils.chunk(elems, n)) == expected


@pytest.mark.parametrize('n', [-1, 0])
def test_chunk_invalid(n):
    with pytest.raises(ValueError):
        list(utils.chunk([], n))


@pytest.mark.parametrize('filename, expected', [
    ('test.jpg', 'image/jpeg'),
    ('test.blabla', 'application/octet-stream'),
])
def test_guess_mimetype(filename, expected):
    assert utils.guess_mimetype(filename, fallback=True) == expected


def test_guess_mimetype_no_fallback():
    with pytest.raises(ValueError):
        utils.guess_mimetype('test.blabla')


@hypothesis.given(number=strategies.integers(min_value=1),
                  base=strategies.integers(min_value=2))
@hypothesis.example(number=125, base=5)
def test_ceil_log_hypothesis(number, base):
    exponent = utils.ceil_log(number, base)
    assert base ** exponent >= number
    # With base=2, number=1 we get exponent=1
    # 2**1 > 1, but 2**0 == 1.
    if exponent > 1:
        assert base ** (exponent - 1) < number


@pytest.mark.parametrize('number, base', [(64, 0), (0, 64), (64, -1),
                                          (-1, 64), (1, 1)])
def test_ceil_log_invalid(number, base):
    with pytest.raises(Exception):  # ValueError/ZeroDivisionError
        math.log(number, base)
    with pytest.raises(ValueError):
        utils.ceil_log(number, base)


@pytest.mark.parametrize('duration, out', [
    ("0", 0),
    ("0s", 0),
    ("0.5s", 500),
    ("59s", 59000),
    ("60", 60),
    ("60.4s", 60400),
    ("1m1s", 61000),
    ("1.5m", 90000),
    ("1m", 60000),
    ("1h", 3_600_000),
    ("0.5h", 1_800_000),
    ("1h1s", 3_601_000),
    ("1h 1s", 3_601_000),
    ("1h1m", 3_660_000),
    ("1h1m1s", 3_661_000),
    ("1h1m10s", 3_670_000),
    ("10h1m10s", 36_070_000),
])
def test_parse_duration(duration, out):
    assert utils.parse_duration(duration) == out


@pytest.mark.parametrize('duration', [
    "-1s",  # No sense to wait for negative seconds
    "-1",
    "34ss",
    "",
    "h",
    "1.s",
    "1.1.1s",
    ".1s",
    ".s",
    "10e5s",
    "5s10m",
])
def test_parse_duration_invalid(duration):
    with pytest.raises(ValueError, match='Invalid duration'):
        utils.parse_duration(duration)


@hypothesis.given(strategies.text())
def test_parse_duration_hypothesis(duration):
    try:
        utils.parse_duration(duration)
    except ValueError:
        pass


@pytest.mark.parametrize('mimetype, extension', [
    ('application/pdf', '.pdf'),  # handled by Python
    ('text/plain', '.txt'),  # wrong in Python 3.6, overridden
    ('application/manifest+json', '.webmanifest'),  # newer
    ('text/xul', '.xul'),  # strict=False
    ('doesnot/exist', None),
])
def test_mimetype_extension(mimetype, extension):
    assert utils.mimetype_extension(mimetype) == extension


class TestCleanupFileContext:

    def test_no_file(self, tmp_path, caplog):
        tmpfile = tmp_path / 'tmp.txt'
        with caplog.at_level(logging.ERROR, 'misc'):
            with utils.cleanup_file(tmpfile):
                pass
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Failed to delete tempfile")
        assert not tmpfile.exists()

    def test_no_error(self, tmp_path):
        tmpfile = tmp_path / 'tmp.txt'
        with tmpfile.open('w'):
            pass
        with utils.cleanup_file(tmpfile):
            pass
        assert not tmpfile.exists()

    def test_error(self, tmp_path):
        tmpfile = tmp_path / 'tmp.txt'
        with tmpfile.open('w'):
            pass
        with pytest.raises(RuntimeError):
            with utils.cleanup_file(tmpfile):
                raise RuntimeError
        assert not tmpfile.exists()

    def test_directory(self, tmp_path, caplog):
        assert tmp_path.is_dir()
        # removal of file fails since it's a directory
        with caplog.at_level(logging.ERROR, 'misc'):
            with utils.cleanup_file(tmp_path):
                pass
        assert len(caplog.messages) == 1
        assert caplog.messages[0].startswith("Failed to delete tempfile")


class TestParseRect:

    @pytest.mark.parametrize('value, expected', [
        ('1x1+0+0', QRect(0, 0, 1, 1)),
        ('123x789+12+34', QRect(12, 34, 123, 789)),
    ])
    def test_valid(self, value, expected):
        assert utils.parse_rect(value) == expected

    @pytest.mark.parametrize('value, message', [
        ('0x0+1+1', "Invalid rectangle"),
        ('1x1-1+1', "String 1x1-1+1 does not match WxH+X+Y"),
        ('1x1+1-1', "String 1x1+1-1 does not match WxH+X+Y"),
        ('1x1', "String 1x1 does not match WxH+X+Y"),
        ('+1+2', "String +1+2 does not match WxH+X+Y"),
        ('1e0x1+0+0', "String 1e0x1+0+0 does not match WxH+X+Y"),
        ('¹x1+0+0', "String ¹x1+0+0 does not match WxH+X+Y"),
    ])
    def test_invalid(self, value, message):
        with pytest.raises(ValueError) as excinfo:
            utils.parse_rect(value)
        assert str(excinfo.value) == message

    @hypothesis.given(strategies.text())
    def test_hypothesis_text(self, s):
        try:
            utils.parse_rect(s)
        except ValueError as e:
            print(e)

    @hypothesis.given(strategies.tuples(
        strategies.integers(),
        strategies.integers(),
        strategies.integers(),
        strategies.integers(),
    ).map(lambda tpl: '{}x{}+{}+{}'.format(*tpl)))
    def test_hypothesis_sophisticated(self, s):
        try:
            utils.parse_rect(s)
        except ValueError as e:
            print(e)

    @hypothesis.given(strategies.from_regex(utils._RECT_PATTERN))
    def test_hypothesis_regex(self, s):
        try:
            utils.parse_rect(s)
        except ValueError as e:
            print(e)
