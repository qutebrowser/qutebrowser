# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import unittest
import datetime
import os.path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from qutebrowser.utils import utils, qtutils
from qutebrowser.test import helpers


class Color(QColor):

    """A QColor with a nicer repr()."""

    def __repr__(self):
        return utils.get_repr(self, constructor=True, red=self.red(),
                              green=self.green(), blue=self.blue(),
                              alpha=self.alpha())


class ElidingTests(unittest.TestCase):

    """Test elide."""

    ELLIPSIS = '\u2026'

    def test_too_small(self):
        """Test eliding to 0 chars which should fail."""
        with self.assertRaises(ValueError):
            utils.elide('foo', 0)

    def test_length_one(self):
        """Test eliding to 1 char which should yield ..."""
        self.assertEqual(utils.elide('foo', 1), self.ELLIPSIS)

    def test_fits(self):
        """Test eliding with a string which fits exactly."""
        self.assertEqual(utils.elide('foo', 3), 'foo')

    def test_elided(self):
        """Test eliding with a string which should get elided."""
        self.assertEqual(utils.elide('foobar', 3), 'fo' + self.ELLIPSIS)


class ReadFileTests(unittest.TestCase):

    """Test read_file."""

    def test_readfile(self):
        """Read a test file."""
        content = utils.read_file(os.path.join('test', 'testfile'))
        self.assertEqual(content.splitlines()[0], "Hello World!")


class InterpolateColorTests(unittest.TestCase):

    """Tests for interpolate_color.

    Attributes:
        white: The Color white as a valid Color for tests.
        white: The Color black as a valid Color for tests.
    """

    def setUp(self):
        self.white = Color('white')
        self.black = Color('black')

    def test_invalid_start(self):
        """Test an invalid start color."""
        with self.assertRaises(qtutils.QtValueError):
            utils.interpolate_color(Color(), self.white, 0)

    def test_invalid_end(self):
        """Test an invalid end color."""
        with self.assertRaises(qtutils.QtValueError):
            utils.interpolate_color(self.white, Color(), 0)

    def test_invalid_percentage(self):
        """Test an invalid percentage."""
        with self.assertRaises(ValueError):
            utils.interpolate_color(self.white, self.white, -1)
        with self.assertRaises(ValueError):
            utils.interpolate_color(self.white, self.white, 101)

    def test_invalid_colorspace(self):
        """Test an invalid colorspace."""
        with self.assertRaises(ValueError):
            utils.interpolate_color(self.white, self.black, 10, QColor.Cmyk)

    def test_valid_percentages_rgb(self):
        """Test 0% and 100% in the RGB colorspace."""
        white = utils.interpolate_color(self.white, self.black, 0, QColor.Rgb)
        black = utils.interpolate_color(self.white, self.black, 100,
                                        QColor.Rgb)
        self.assertEqual(Color(white), self.white)
        self.assertEqual(Color(black), self.black)

    def test_valid_percentages_hsv(self):
        """Test 0% and 100% in the HSV colorspace."""
        white = utils.interpolate_color(self.white, self.black, 0, QColor.Hsv)
        black = utils.interpolate_color(self.white, self.black, 100,
                                        QColor.Hsv)
        self.assertEqual(Color(white), self.white)
        self.assertEqual(Color(black), self.black)

    def test_valid_percentages_hsl(self):
        """Test 0% and 100% in the HSL colorspace."""
        white = utils.interpolate_color(self.white, self.black, 0, QColor.Hsl)
        black = utils.interpolate_color(self.white, self.black, 100,
                                        QColor.Hsl)
        self.assertEqual(Color(white), self.white)
        self.assertEqual(Color(black), self.black)

    def test_interpolation_rgb(self):
        """Test an interpolation in the RGB colorspace."""
        color = utils.interpolate_color(Color(0, 40, 100), Color(0, 20, 200),
                                        50, QColor.Rgb)
        self.assertEqual(Color(color), Color(0, 30, 150))

    def test_interpolation_hsv(self):
        """Test an interpolation in the HSV colorspace."""
        start = Color()
        stop = Color()
        start.setHsv(0, 40, 100)
        stop.setHsv(0, 20, 200)
        color = utils.interpolate_color(start, stop, 50, QColor.Hsv)
        expected = Color()
        expected.setHsv(0, 30, 150)
        self.assertEqual(Color(color), expected)

    def test_interpolation_hsl(self):
        """Test an interpolation in the HSL colorspace."""
        start = Color()
        stop = Color()
        start.setHsl(0, 40, 100)
        stop.setHsl(0, 20, 200)
        color = utils.interpolate_color(start, stop, 50, QColor.Hsl)
        expected = Color()
        expected.setHsl(0, 30, 150)
        self.assertEqual(Color(color), expected)


class FormatSecondsTests(unittest.TestCase):

    """Tests for format_seconds.

    Class attributes:
        TESTS: A list of (input, output) tuples.
    """

    TESTS = [
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
    ]

    def test_format_seconds(self):
        """Test format_seconds with several tests."""
        for seconds, out in self.TESTS:
            with self.subTest(seconds=seconds):
                self.assertEqual(utils.format_seconds(seconds), out)


class FormatTimedeltaTests(unittest.TestCase):

    """Tests for format_timedelta.

    Class attributes:
        TESTS: A list of (input, output) tuples.
    """

    TESTS = [
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
    ]

    def test_format_seconds(self):
        """Test format_seconds with several tests."""
        for td, out in self.TESTS:
            with self.subTest(td=td):
                self.assertEqual(utils.format_timedelta(td), out)


class FormatSizeTests(unittest.TestCase):

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

    def test_format_size(self):
        """Test format_size with several tests."""
        for size, out in self.TESTS:
            with self.subTest(size=size):
                self.assertEqual(utils.format_size(size), out)

    def test_suffix(self):
        """Test the suffix option."""
        for size, out in self.TESTS:
            with self.subTest(size=size):
                self.assertEqual(utils.format_size(size, suffix='B'),
                                 out + 'B')

    def test_base(self):
        """Test with an alternative base."""
        kilo_tests = [(999, '999.00'), (1000, '1.00k'), (1010, '1.01k')]
        for size, out in kilo_tests:
            with self.subTest(size=size):
                self.assertEqual(utils.format_size(size, base=1000), out)


class KeyToStringTests(unittest.TestCase):

    """Test key_to_string."""

    def test_unicode_garbage_keys(self):
        """Test a special key where QKeyEvent::toString works incorrectly."""
        self.assertEqual(utils.key_to_string(Qt.Key_Blue), 'Blue')

    def test_backtab(self):
        """Test if backtab is normalized to tab correctly."""
        self.assertEqual(utils.key_to_string(Qt.Key_Backtab), 'Tab')

    def test_escape(self):
        """Test if escape is normalized to escape correctly."""
        self.assertEqual(utils.key_to_string(Qt.Key_Escape), 'Escape')

    def test_letter(self):
        """Test a simple letter key."""
        self.assertEqual(utils.key_to_string(Qt.Key_A), 'A')

    def test_unicode(self):
        """Test a printable unicode key."""
        self.assertEqual(utils.key_to_string(Qt.Key_degree), '°')

    def test_special(self):
        """Test a non-printable key handled by QKeyEvent::toString."""
        self.assertEqual(utils.key_to_string(Qt.Key_F1), 'F1')


class KeyEventToStringTests(unittest.TestCase):

    """Test keyevent_to_string."""

    def test_only_control(self):
        """Test keyevent when only control is pressed."""
        evt = helpers.fake_keyevent(key=Qt.Key_Control,
                                    modifiers=Qt.ControlModifier)
        self.assertIsNone(utils.keyevent_to_string(evt))

    def test_only_hyper_l(self):
        """Test keyevent when only Hyper_L is pressed."""
        evt = helpers.fake_keyevent(key=Qt.Key_Hyper_L,
                                    modifiers=Qt.MetaModifier)
        self.assertIsNone(utils.keyevent_to_string(evt))

    def test_only_key(self):
        """Test with a simple key pressed."""
        evt = helpers.fake_keyevent(key=Qt.Key_A)
        self.assertEqual(utils.keyevent_to_string(evt), 'A')

    def test_key_and_modifier(self):
        """Test with key and modifier pressed."""
        evt = helpers.fake_keyevent(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        self.assertEqual(utils.keyevent_to_string(evt), 'Ctrl+A')

    def test_key_and_modifiers(self):
        """Test with key and multiple modifier pressed."""
        evt = helpers.fake_keyevent(
            key=Qt.Key_A, modifiers=(Qt.ControlModifier | Qt.AltModifier |
                                     Qt.MetaModifier | Qt.ShiftModifier))
        if sys.platform == 'darwin':
            self.assertEqual(utils.keyevent_to_string(evt),
                             'Ctrl+Alt+Shift+A')
        else:
            self.assertEqual(utils.keyevent_to_string(evt),
                             'Ctrl+Alt+Meta+Shift+A')


class NormalizeTests(unittest.TestCase):

    """Test normalize_keystr."""

    def test_normalize(self):
        """Test normalize with some strings."""
        strings = (
            ('Control+x', 'ctrl+x'),
            ('Windows+x', 'meta+x'),
            ('Mod1+x', 'alt+x'),
            ('Mod4+x', 'meta+x'),
            ('Control--', 'ctrl+-'),
            ('Windows++', 'meta++'),
        )
        for orig, repl in strings:
            with self.subTest(orig=orig):
                self.assertEqual(utils.normalize_keystr(orig), repl)


class IsEnumTests(unittest.TestCase):

    """Test is_enum."""

    def test_enum(self):
        """Test is_enum with an enum."""
        e = enum.Enum('Foo', 'bar, baz')
        self.assertTrue(utils.is_enum(e))

    def test_class(self):
        """Test is_enum with a non-enum class."""
        class Test:

            """Test class for is_enum."""

            pass
        self.assertFalse(utils.is_enum(Test))

    def test_object(self):
        """Test is_enum with a non-enum object."""
        self.assertFalse(utils.is_enum(23))


class RaisesTests(unittest.TestCase):

    """Test raises."""

    def do_raise(self):
        """Helper function which raises an exception."""
        raise Exception

    def do_nothing(self):
        """Helper function which does nothing."""
        pass

    def test_raises_single_exc_true(self):
        """Test raises with a single exception which gets raised."""
        self.assertTrue(utils.raises(ValueError, int, 'a'))

    def test_raises_single_exc_false(self):
        """Test raises with a single exception which does not get raised."""
        self.assertFalse(utils.raises(ValueError, int, '1'))

    def test_raises_multiple_exc_true(self):
        """Test raises with multiple exceptions which get raised."""
        self.assertTrue(utils.raises((ValueError, TypeError), int, 'a'))
        self.assertTrue(utils.raises((ValueError, TypeError), int, None))

    def test_raises_multiple_exc_false(self):
        """Test raises with multiple exceptions which do not get raised."""
        self.assertFalse(utils.raises((ValueError, TypeError), int, '1'))

    def test_no_args_true(self):
        """Test with no args and an exception which gets raised."""
        self.assertTrue(utils.raises(Exception, self.do_raise))

    def test_no_args_false(self):
        """Test with no args and an exception which does not get raised."""
        self.assertFalse(utils.raises(Exception, self.do_nothing))

    def test_unrelated_exception(self):
        """Test with an unrelated exception."""
        with self.assertRaises(Exception):
            utils.raises(ValueError, self.do_raise)


class ForceEncodingTests(unittest.TestCase):

    """Test force_encoding."""

    def test_fitting_ascii(self):
        """Test with a text fitting into ASCII."""
        text = 'hello world'
        self.assertEqual(utils.force_encoding(text, 'ascii'), text)

    def test_fitting_utf8(self):
        """Test with a text fitting into utf-8."""
        text = 'hellö wörld'
        self.assertEqual(utils.force_encoding(text, 'utf-8'), text)

    def test_not_fitting_ascii(self):
        """Test with a text not fitting into ASCII."""
        text = 'hellö wörld'
        self.assertEqual(utils.force_encoding(text, 'ascii'), 'hell? w?rld')


class NewestSliceTests(unittest.TestCase):

    """Test newest_slice."""

    def test_count_minus_two(self):
        """Test with a count of -2."""
        with self.assertRaises(ValueError):
            utils.newest_slice([], -2)

    def test_count_minus_one(self):
        """Test with a count of -1 (all elements)."""
        items = range(20)
        sliced = utils.newest_slice(items, -1)
        self.assertEqual(list(sliced), list(items))

    def test_count_zero(self):
        """Test with a count of 0 (no elements)."""
        items = range(20)
        sliced = utils.newest_slice(items, 0)
        self.assertEqual(list(sliced), [])

    def test_count_much_smaller(self):
        """Test with a count which is much smaller than the iterable."""
        items = range(20)
        sliced = utils.newest_slice(items, 5)
        self.assertEqual(list(sliced), [15, 16, 17, 18, 19])

    def test_count_smaller(self):
        """Test with a count which is exactly one smaller."""
        items = range(5)
        sliced = utils.newest_slice(items, 4)
        self.assertEqual(list(sliced), [1, 2, 3, 4])

    def test_count_equal(self):
        """Test with a count which is just as large as the iterable."""
        items = range(5)
        sliced = utils.newest_slice(items, 5)
        self.assertEqual(list(sliced), list(items))

    def test_count_bigger(self):
        """Test with a count which is one bigger than the iterable."""
        items = range(5)
        sliced = utils.newest_slice(items, 6)
        self.assertEqual(list(sliced), list(items))

    def test_count_much_bigger(self):
        """Test with a count which is much bigger than the iterable."""
        items = range(5)
        sliced = utils.newest_slice(items, 50)
        self.assertEqual(list(sliced), list(items))


if __name__ == '__main__':
    unittest.main()
