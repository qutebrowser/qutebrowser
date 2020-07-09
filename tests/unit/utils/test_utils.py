# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.utils."""

import sys
import enum
import os.path
import io
import logging
import functools
import socket
import re
import shlex
import math

import pkg_resources
import attr
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor, QClipboard
import pytest
import hypothesis
from hypothesis import strategies

import qutebrowser
import qutebrowser.utils  # for test_qualname
from qutebrowser.utils import utils, qtutils, version, usertypes


ELLIPSIS = '\u2026'


class Color(QColor):

    """A QColor with a nicer repr()."""

    def __repr__(self):
        return utils.get_repr(self, constructor=True, red=self.red(),
                              green=self.green(), blue=self.blue(),
                              alpha=self.alpha())


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


@pytest.fixture(params=[True, False])
def freezer(request, monkeypatch):
    if request.param and not getattr(sys, 'frozen', False):
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setattr(sys, 'executable', qutebrowser.__file__)
    elif not request.param and getattr(sys, 'frozen', False):
        # Want to test unfrozen tests, but we are frozen
        pytest.skip("Can't run with sys.frozen = True!")


@pytest.mark.usefixtures('freezer')
class TestReadFile:

    """Test read_file."""

    def test_readfile(self):
        """Read a test file."""
        content = utils.read_file(os.path.join('utils', 'testfile'))
        assert content.splitlines()[0] == "Hello World!"

    @pytest.mark.parametrize('filename', ['javascript/scroll.js',
                                          'html/error.html'])
    def test_read_cached_file(self, mocker, filename):
        utils.preload_resources()
        m = mocker.patch('pkg_resources.resource_string')
        utils.read_file(filename)
        m.assert_not_called()

    def test_readfile_binary(self):
        """Read a test file in binary mode."""
        content = utils.read_file(os.path.join('utils', 'testfile'),
                                  binary=True)
        assert content.splitlines()[0] == b"Hello World!"


@pytest.mark.usefixtures('freezer')
def test_resource_filename():
    """Read a test file."""
    filename = utils.resource_filename(os.path.join('utils', 'testfile'))
    with open(filename, 'r', encoding='utf-8') as f:
        assert f.read().splitlines()[0] == "Hello World!"


class TestInterpolateColor:

    """Tests for interpolate_color.

    Attributes:
        white: The Color white as a valid Color for tests.
        white: The Color black as a valid Color for tests.
    """

    @attr.s
    class Colors:

        white = attr.ib()
        black = attr.ib()

    @pytest.fixture
    def colors(self):
        """Example colors to be used."""
        return self.Colors(Color('white'), Color('black'))

    def test_invalid_start(self, colors):
        """Test an invalid start color."""
        with pytest.raises(qtutils.QtValueError):
            utils.interpolate_color(Color(), colors.white, 0)

    def test_invalid_end(self, colors):
        """Test an invalid end color."""
        with pytest.raises(qtutils.QtValueError):
            utils.interpolate_color(colors.white, Color(), 0)

    @pytest.mark.parametrize('perc', [-1, 101])
    def test_invalid_percentage(self, colors, perc):
        """Test an invalid percentage."""
        with pytest.raises(ValueError):
            utils.interpolate_color(colors.white, colors.white, perc)

    def test_invalid_colorspace(self, colors):
        """Test an invalid colorspace."""
        with pytest.raises(ValueError):
            utils.interpolate_color(colors.white, colors.black, 10,
                                    QColor.Cmyk)

    @pytest.mark.parametrize('colorspace', [QColor.Rgb, QColor.Hsv,
                                            QColor.Hsl])
    def test_0_100(self, colors, colorspace):
        """Test 0% and 100% in different colorspaces."""
        white = utils.interpolate_color(colors.white, colors.black, 0,
                                        colorspace)
        black = utils.interpolate_color(colors.white, colors.black, 100,
                                        colorspace)
        assert Color(white) == colors.white
        assert Color(black) == colors.black

    def test_interpolation_rgb(self):
        """Test an interpolation in the RGB colorspace."""
        color = utils.interpolate_color(Color(0, 40, 100), Color(0, 20, 200),
                                        50, QColor.Rgb)
        assert Color(color) == Color(0, 30, 150)

    def test_interpolation_hsv(self):
        """Test an interpolation in the HSV colorspace."""
        start = Color()
        stop = Color()
        start.setHsv(0, 40, 100)
        stop.setHsv(0, 20, 200)
        color = utils.interpolate_color(start, stop, 50, QColor.Hsv)
        expected = Color()
        expected.setHsv(0, 30, 150)
        assert Color(color) == expected

    def test_interpolation_hsl(self):
        """Test an interpolation in the HSL colorspace."""
        start = Color()
        stop = Color()
        start.setHsl(0, 40, 100)
        stop.setHsl(0, 20, 200)
        color = utils.interpolate_color(start, stop, 50, QColor.Hsl)
        expected = Color()
        expected.setHsl(0, 30, 150)
        assert Color(color) == expected

    @pytest.mark.parametrize('percentage, expected', [
        (0, (0, 0, 0)),
        (99, (0, 0, 0)),
        (100, (255, 255, 255)),
    ])
    def test_interpolation_none(self, percentage, expected):
        """Test an interpolation with a gradient turned off."""
        color = utils.interpolate_color(Color(0, 0, 0), Color(255, 255, 255),
                                        percentage, None)
        assert isinstance(color, QColor)
        assert Color(color) == Color(*expected)


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
        e = enum.Enum('Foo', 'bar, baz')
        assert utils.is_enum(e)

    def test_class(self):
        """Test is_enum with a non-enum class."""
        class Test:

            """Test class for is_enum."""

        assert not utils.is_enum(Test)

    def test_object(self):
        """Test is_enum with a non-enum object."""
        assert not utils.is_enum(23)


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
])
def test_sanitize_filename(inp, expected, monkeypatch):
    assert utils.sanitize_filename(inp) == expected


@pytest.mark.fake_os('windows')
def test_sanitize_filename_empty_replacement():
    name = '/<Bad File>/'
    assert utils.sanitize_filename(name, replacement=None) == 'Bad File'


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


def test_random_port():
    port = utils.random_port()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', port))
    sock.close()


class TestOpenFile:

    @pytest.mark.not_frozen
    def test_cmdline_without_argument(self, caplog, config_stub):
        executable = shlex.quote(sys.executable)
        cmdline = '{} -c pass'.format(executable)
        utils.open_file('/foo/bar', cmdline)
        result = caplog.messages[0]
        assert re.fullmatch(
            r'Opening /foo/bar with \[.*python.*/foo/bar.*\]', result)

    @pytest.mark.not_frozen
    def test_cmdline_with_argument(self, caplog, config_stub):
        executable = shlex.quote(sys.executable)
        cmdline = '{} -c pass {{}} raboof'.format(executable)
        utils.open_file('/foo/bar', cmdline)
        result = caplog.messages[0]
        assert re.fullmatch(
            r"Opening /foo/bar with \[.*python.*/foo/bar.*'raboof'\]", result)

    @pytest.mark.not_frozen
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

    @pytest.fixture
    def sandbox_patch(self, monkeypatch):
        info = version.DistributionInfo(
            id='org.kde.Platform',
            parsed=version.Distribution.kde_flatpak,
            version=pkg_resources.parse_version('5.12'),
            pretty='Unknown')
        monkeypatch.setattr(version, 'distribution',
                            lambda: info)

    def test_cmdline_sandboxed(self, sandbox_patch,
                               config_stub, message_mock, caplog):
        with caplog.at_level(logging.ERROR):
            utils.open_file('/foo/bar', 'custom_cmd')
        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text == 'Cannot spawn download dispatcher from sandbox'

    @pytest.mark.not_frozen
    def test_setting_override_sandboxed(self, sandbox_patch, openurl_mock,
                                        caplog, config_stub):
        config_stub.val.downloads.open_dispatcher = 'test'

        with caplog.at_level(logging.WARNING):
            utils.open_file('/foo/bar')

        assert caplog.messages[1] == ('Ignoring download dispatcher from '
                                      'config in sandbox environment')
        openurl_mock.assert_called_with(QUrl('file:///foo/bar'))

    def test_system_default_sandboxed(self, config_stub, openurl_mock,
                                      sandbox_patch):
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

    def test_load_file(self, tmpdir):
        tmpfile = tmpdir / 'foo.yml'
        tmpfile.write('[1, 2]')
        with tmpfile.open(encoding='utf-8') as f:
            assert utils.yaml_load(f) == [1, 2]

    def test_dump(self):
        assert utils.yaml_dump([1, 2]) == '- 1\n- 2\n'

    def test_dump_file(self, tmpdir):
        tmpfile = tmpdir / 'foo.yml'
        with tmpfile.open('w', encoding='utf-8') as f:
            utils.yaml_dump([1, 2], f)
        assert tmpfile.read() == '- 1\n- 2\n'


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


@pytest.mark.parametrize('skip', [True, False])
def test_libgl_workaround(monkeypatch, skip):
    if skip:
        monkeypatch.setenv('QUTE_SKIP_LIBGL_WORKAROUND', '1')
    utils.libgl_workaround()  # Just make sure it doesn't crash.
