# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import datetime
import os.path
import io
import logging
import functools
import collections

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QClipboard
import pytest

import qutebrowser
import qutebrowser.utils  # for test_qualname
from qutebrowser.utils import utils, qtutils


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


@pytest.fixture(params=[True, False])
def freezer(request, monkeypatch):
    if request.param and not getattr(sys, 'frozen', False):
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setattr('sys.executable', qutebrowser.__file__)
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


class Patcher:

    """Helper for TestActuteWarning.

    Attributes:
        monkeypatch: The pytest monkeypatch fixture.
    """

    def __init__(self, monkeypatch):
        self.monkeypatch = monkeypatch

    def patch_platform(self, platform='linux'):
        """Patch sys.platform."""
        self.monkeypatch.setattr('sys.platform', platform)

    def patch_exists(self, exists=True):
        """Patch os.path.exists."""
        self.monkeypatch.setattr('qutebrowser.utils.utils.os.path.exists',
                                 lambda path: exists)

    def patch_version(self, version='5.2.0'):
        """Patch Qt version."""
        self.monkeypatch.setattr('qutebrowser.utils.utils.qtutils.qVersion',
                                 lambda: version)

    def patch_file(self, data):
        """Patch open() to return the given data."""
        fake_file = io.StringIO(data)
        self.monkeypatch.setattr(utils, 'open',
                                 lambda filename, mode, encoding: fake_file,
                                 raising=False)

    def patch_all(self, data):
        """Patch everything so the issue would exist."""
        self.patch_platform()
        self.patch_exists()
        self.patch_version()
        self.patch_file(data)


class TestActuteWarning:

    """Test actute_warning."""

    @pytest.fixture
    def patcher(self, monkeypatch):
        """Fixture providing a Patcher helper."""
        return Patcher(monkeypatch)

    def test_non_linux(self, patcher, capsys):
        """Test with a non-Linux OS."""
        patcher.patch_platform('toaster')
        utils.actute_warning()
        out, err = capsys.readouterr()
        assert not out
        assert not err

    def test_no_compose(self, patcher, capsys):
        """Test with no compose file."""
        patcher.patch_platform()
        patcher.patch_exists(False)
        utils.actute_warning()
        out, err = capsys.readouterr()
        assert not out
        assert not err

    def test_newer_qt(self, patcher, capsys):
        """Test with compose file but newer Qt version."""
        patcher.patch_platform()
        patcher.patch_exists()
        patcher.patch_version('5.4')
        utils.actute_warning()
        out, err = capsys.readouterr()
        assert not out
        assert not err

    def test_no_match(self, patcher, capsys):
        """Test with compose file and affected Qt but no match."""
        patcher.patch_all('foobar')
        utils.actute_warning()
        out, err = capsys.readouterr()
        assert not out
        assert not err

    def test_empty(self, patcher, capsys):
        """Test with empty compose file."""
        patcher.patch_all(None)
        utils.actute_warning()
        out, err = capsys.readouterr()
        assert not out
        assert not err

    def test_match(self, patcher, capsys):
        """Test with compose file and affected Qt and a match."""
        patcher.patch_all('foobar\n<dead_actute>\nbaz')
        utils.actute_warning()
        out, err = capsys.readouterr()
        assert out.startswith('Note: If you got a')
        assert not err

    def test_match_stdout_none(self, monkeypatch, patcher, capsys):
        """Test with a match and stdout being None."""
        patcher.patch_all('foobar\n<dead_actute>\nbaz')
        monkeypatch.setattr('sys.stdout', None)
        utils.actute_warning()

    def test_unreadable(self, mocker, patcher, capsys, caplog):
        """Test with an unreadable compose file."""
        patcher.patch_platform()
        patcher.patch_exists()
        patcher.patch_version()
        mocker.patch('qutebrowser.utils.utils.open', side_effect=OSError,
                     create=True)

        with caplog.at_level(logging.ERROR, 'init'):
            utils.actute_warning()

        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Failed to read Compose file'
        out, _err = capsys.readouterr()
        assert not out


class TestInterpolateColor:

    """Tests for interpolate_color.

    Attributes:
        white: The Color white as a valid Color for tests.
        white: The Color black as a valid Color for tests.
    """

    Colors = collections.namedtuple('Colors', ['white', 'black'])

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

    def test_invalid_percentage(self, colors):
        """Test an invalid percentage."""
        with pytest.raises(ValueError):
            utils.interpolate_color(colors.white, colors.white, -1)
        with pytest.raises(ValueError):
            utils.interpolate_color(colors.white, colors.white, 101)

    def test_invalid_colorspace(self, colors):
        """Test an invalid colorspace."""
        with pytest.raises(ValueError):
            utils.interpolate_color(colors.white, colors.black, 10,
                                    QColor.Cmyk)

    def test_valid_percentages_rgb(self, colors):
        """Test 0% and 100% in the RGB colorspace."""
        white = utils.interpolate_color(colors.white, colors.black, 0,
                                        QColor.Rgb)
        black = utils.interpolate_color(colors.white, colors.black, 100,
                                        QColor.Rgb)
        assert Color(white) == colors.white
        assert Color(black) == colors.black

    def test_valid_percentages_hsv(self, colors):
        """Test 0% and 100% in the HSV colorspace."""
        white = utils.interpolate_color(colors.white, colors.black, 0,
                                        QColor.Hsv)
        black = utils.interpolate_color(colors.white, colors.black, 100,
                                        QColor.Hsv)
        assert Color(white) == colors.white
        assert Color(black) == colors.black

    def test_valid_percentages_hsl(self, colors):
        """Test 0% and 100% in the HSL colorspace."""
        white = utils.interpolate_color(colors.white, colors.black, 0,
                                        QColor.Hsl)
        black = utils.interpolate_color(colors.white, colors.black, 100,
                                        QColor.Hsl)
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


@pytest.mark.parametrize('td, out', [
    (datetime.timedelta(seconds=-1), '-1s'),
    (datetime.timedelta(seconds=0), '0s'),
    (datetime.timedelta(seconds=59), '59s'),
    (datetime.timedelta(seconds=120), '2m'),
    (datetime.timedelta(seconds=60.4), '1m'),
    (datetime.timedelta(seconds=63), '1m 3s'),
    (datetime.timedelta(seconds=-64), '-1m 4s'),
    (datetime.timedelta(seconds=3599), '59m 59s'),
    (datetime.timedelta(seconds=3600), '1h'),
    (datetime.timedelta(seconds=3605), '1h 5s'),
    (datetime.timedelta(seconds=3723), '1h 2m 3s'),
    (datetime.timedelta(seconds=3780), '1h 3m'),
    (datetime.timedelta(seconds=36000), '10h'),
])
def test_format_timedelta(td, out):
    assert utils.format_timedelta(td) == out


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


class TestKeyToString:

    """Test key_to_string."""

    @pytest.mark.parametrize('key, expected', [
        (Qt.Key_Blue, 'Blue'),
        (Qt.Key_Backtab, 'Tab'),
        (Qt.Key_Escape, 'Escape'),
        (Qt.Key_A, 'A'),
        (Qt.Key_degree, '°'),
        (Qt.Key_Meta, 'Meta'),
    ])
    def test_normal(self, key, expected):
        """Test a special key where QKeyEvent::toString works incorrectly."""
        assert utils.key_to_string(key) == expected

    def test_missing(self, monkeypatch):
        """Test with a missing key."""
        monkeypatch.delattr('qutebrowser.utils.utils.Qt.Key_Blue')
        # We don't want to test the key which is actually missing - we only
        # want to know if the mapping still behaves properly.
        assert utils.key_to_string(Qt.Key_A) == 'A'

    def test_all(self):
        """Make sure there's some sensible output for all keys."""
        for name, value in sorted(vars(Qt).items()):
            if not isinstance(value, Qt.Key):
                continue
            print(name)
            string = utils.key_to_string(value)
            assert string
            string.encode('utf-8')  # make sure it's encodable


class TestKeyEventToString:

    """Test keyevent_to_string."""

    def test_only_control(self, fake_keyevent_factory):
        """Test keyeevent when only control is pressed."""
        evt = fake_keyevent_factory(key=Qt.Key_Control,
                                    modifiers=Qt.ControlModifier)
        assert utils.keyevent_to_string(evt) is None

    def test_only_hyper_l(self, fake_keyevent_factory):
        """Test keyeevent when only Hyper_L is pressed."""
        evt = fake_keyevent_factory(key=Qt.Key_Hyper_L,
                                    modifiers=Qt.MetaModifier)
        assert utils.keyevent_to_string(evt) is None

    def test_only_key(self, fake_keyevent_factory):
        """Test with a simple key pressed."""
        evt = fake_keyevent_factory(key=Qt.Key_A)
        assert utils.keyevent_to_string(evt) == 'A'

    def test_key_and_modifier(self, fake_keyevent_factory):
        """Test with key and modifier pressed."""
        evt = fake_keyevent_factory(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        expected = 'Meta+A' if sys.platform == 'darwin' else 'Ctrl+A'
        assert utils.keyevent_to_string(evt) == expected

    def test_key_and_modifiers(self, fake_keyevent_factory):
        """Test with key and multiple modifiers pressed."""
        evt = fake_keyevent_factory(
            key=Qt.Key_A, modifiers=(Qt.ControlModifier | Qt.AltModifier |
                                     Qt.MetaModifier | Qt.ShiftModifier))
        assert utils.keyevent_to_string(evt) == 'Ctrl+Alt+Meta+Shift+A'

    def test_mac(self, monkeypatch, fake_keyevent_factory):
        """Test with a simulated mac."""
        monkeypatch.setattr('sys.platform', 'darwin')
        evt = fake_keyevent_factory(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        assert utils.keyevent_to_string(evt) == 'Meta+A'


@pytest.mark.parametrize('keystr, expected', [
    ('<Control-x>', utils.KeyInfo(Qt.Key_X, Qt.ControlModifier, '')),
    ('<Meta-x>', utils.KeyInfo(Qt.Key_X, Qt.MetaModifier, '')),
    ('<Ctrl-Alt-y>',
        utils.KeyInfo(Qt.Key_Y, Qt.ControlModifier | Qt.AltModifier, '')),
    ('x', utils.KeyInfo(Qt.Key_X, Qt.NoModifier, 'x')),
    ('X', utils.KeyInfo(Qt.Key_X, Qt.ShiftModifier, 'X')),
    ('<Escape>', utils.KeyInfo(Qt.Key_Escape, Qt.NoModifier, '')),

    ('foobar', utils.KeyParseError),
    ('x, y', utils.KeyParseError),
    ('xyz', utils.KeyParseError),
    ('Escape', utils.KeyParseError),
    ('<Ctrl-x>, <Ctrl-y>', utils.KeyParseError),
])
def test_parse_single_key(keystr, expected):
    if expected is utils.KeyParseError:
        with pytest.raises(utils.KeyParseError):
            utils._parse_single_key(keystr)
    else:
        assert utils._parse_single_key(keystr) == expected


@pytest.mark.parametrize('keystr, expected', [
    ('<Control-x>', [utils.KeyInfo(Qt.Key_X, Qt.ControlModifier, '')]),
    ('x', [utils.KeyInfo(Qt.Key_X, Qt.NoModifier, 'x')]),
    ('xy', [utils.KeyInfo(Qt.Key_X, Qt.NoModifier, 'x'),
            utils.KeyInfo(Qt.Key_Y, Qt.NoModifier, 'y')]),

    ('<Control-x><Meta-x>', utils.KeyParseError),
])
def test_parse_keystring(keystr, expected):
    if expected is utils.KeyParseError:
        with pytest.raises(utils.KeyParseError):
            utils.parse_keystring(keystr)
    else:
        assert utils.parse_keystring(keystr) == expected


@pytest.mark.parametrize('orig, repl', [
    ('Control+x', 'ctrl+x'),
    ('Windows+x', 'meta+x'),
    ('Mod1+x', 'alt+x'),
    ('Mod4+x', 'meta+x'),
    ('Control--', 'ctrl+-'),
    ('Windows++', 'meta++'),
    ('ctrl-x', 'ctrl+x'),
    ('control+x', 'ctrl+x')
])
def test_normalize_keystr(orig, repl):
    assert utils.normalize_keystr(orig) == repl


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

    @pytest.yield_fixture(autouse=True)
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

    pass


def excepthook(_exc, _val, _tb):
    return


def excepthook_2(_exc, _val, _tb):
    return


class TestDisabledExcepthook:

    """Test disabled_excepthook.

    This doesn't test much as some things are untestable without triggering
    the excepthook (which is hard to test).
    """

    @pytest.yield_fixture(autouse=True)
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
        assert len(caplog.records) == 1
        expected = 'Error in test_utils.TestPreventExceptions.func_raising'
        actual = caplog.records[0].message
        assert actual == expected

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

    pass


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
        pass


def qualname_func(_blah):
    """Test function for test_qualname."""
    pass


QUALNAME_OBJ = QualnameObj()


@pytest.mark.parametrize('obj, expected', [
    (QUALNAME_OBJ, repr(QUALNAME_OBJ)),  # instance - unknown
    (QualnameObj, 'test_utils.QualnameObj'),  # class
    (QualnameObj.func, 'test_utils.QualnameObj.func'),  # unbound method
    (QualnameObj().func, 'test_utils.QualnameObj.func'),  # bound method
    (qualname_func, 'test_utils.qualname_func'),  # function
    (functools.partial(qualname_func, True), 'test_utils.qualname_func'),
    (qutebrowser, 'qutebrowser'),  # module
    (qutebrowser.utils, 'qutebrowser.utils'),  # submodule
    (utils, 'qutebrowser.utils.utils'),  # submodule (from-import)
], ids=['instance', 'class', 'unbound-method', 'bound-method', 'function',
        'partial', 'module', 'submodule', 'from-import'])
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

            pass

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
        pass

    def test_raises_single_exc_true(self):
        """Test raises with a single exception which gets raised."""
        assert utils.raises(ValueError, int, 'a')

    def test_raises_single_exc_false(self):
        """Test raises with a single exception which does not get raised."""
        assert not utils.raises(ValueError, int, '1')

    def test_raises_multiple_exc_true(self):
        """Test raises with multiple exceptions which get raised."""
        assert utils.raises((ValueError, TypeError), int, 'a')
        assert utils.raises((ValueError, TypeError), int, None)

    def test_raises_multiple_exc_false(self):
        """Test raises with multiple exceptions which do not get raised."""
        assert not utils.raises((ValueError, TypeError), int, '1')

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
    ('normal.txt', 'normal.txt'),
    ('user/repo issues.mht', 'user_repo issues.mht'),
    ('<Test\\File> - "*?:|', '_Test_File_ - _____'),
])
def test_sanitize_filename(inp, expected):
    assert utils.sanitize_filename(inp) == expected


def test_sanitize_filename_empty_replacement():
    name = '/<Bad File>/'
    assert utils.sanitize_filename(name, replacement=None) == 'Bad File'


class TestNewestSlice:

    """Test newest_slice."""

    def test_count_minus_two(self):
        """Test with a count of -2."""
        with pytest.raises(ValueError):
            utils.newest_slice([], -2)

    @pytest.mark.parametrize('items, count, expected', [
        # Count of -1 (all elements).
        (range(20), -1, range(20)),
        # Count of 0 (no elements).
        (range(20), 0, []),
        # Count which is much smaller than the iterable.
        (range(20), 5, [15, 16, 17, 18, 19]),
        # Count which is exactly one smaller."""
        (range(5), 4, [1, 2, 3, 4]),
        # Count which is just as large as the iterable."""
        (range(5), 5, range(5)),
        # Count which is one bigger than the iterable.
        (range(5), 6, range(5)),
        # Count which is much bigger than the iterable.
        (range(5), 50, range(5)),
    ])
    def test_good(self, items, count, expected):
        """Test slices which shouldn't raise an exception."""
        sliced = utils.newest_slice(items, count)
        assert list(sliced) == list(expected)


class TestGetSetClipboard:

    @pytest.fixture(autouse=True)
    def clipboard_mock(self, mocker):
        m = mocker.patch('qutebrowser.utils.utils.QApplication.clipboard',
                         autospec=True)
        clipboard = m()
        clipboard.text.return_value = 'mocked clipboard text'
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
        assert caplog.records[0].message == expected

    def test_get(self):
        assert utils.get_clipboard() == 'mocked clipboard text'

    def test_get_unsupported_selection(self, clipboard_mock):
        clipboard_mock.supportsSelection.return_value = False
        with pytest.raises(utils.SelectionUnsupportedError):
            utils.get_clipboard(selection=True)

    @pytest.mark.parametrize('selection', [True, False])
    def test_get_fake_clipboard(self, selection):
        utils.fake_clipboard = 'fake clipboard text'
        utils.get_clipboard(selection=selection)
        assert utils.fake_clipboard is None

    @pytest.mark.parametrize('selection', [True, False])
    def test_supports_selection(self, clipboard_mock, selection):
        clipboard_mock.supportsSelection.return_value = selection
        assert utils.supports_selection() == selection


@pytest.mark.parametrize('keystr, expected', [
    ('<Control-x>', True),
    ('<Meta-x>', True),
    ('<Ctrl-Alt-y>', True),
    ('x', False),
    ('X', False),
    ('<Escape>', True),
    ('foobar', False),
    ('foo>', False),
    ('<foo', False),
    ('<<', False),
])
def test_is_special_key(keystr, expected):
    assert utils.is_special_key(keystr) == expected
