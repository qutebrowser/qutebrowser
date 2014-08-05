# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.misc."""

import os
import sys
import shutil
import unittest
import os.path
from tempfile import mkdtemp

from PyQt5.QtCore import QStandardPaths, QCoreApplication, Qt
from PyQt5.QtGui import QColor

import qutebrowser.utils.misc as utils
from qutebrowser.test.helpers import environ_set_temp, fake_keyevent
from qutebrowser.utils.qt import QtValueError


class Color(QColor):

    """A QColor with a nicer repr()."""

    def __repr__(self):
        return 'Color({}, {}, {}, {})'.format(
            self.red(), self.green(), self.blue(), self.alpha())


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
        """Read a testfile."""
        content = utils.read_file(os.path.join('test', 'testfile'))
        self.assertEqual(content.splitlines()[0], "Hello World!")


class DottedGetattrTests(unittest.TestCase):

    """Test dotted_getattr.

    Attributes:
        test: Test class instance for getattr.
    """

    class Test:

        """Sample class used to test dotted_getattr."""

        foo = None

    class Test2:

        """Sample class used to test dotted_getattr."""

        bar = 1

    def setUp(self):
        self.test = self.Test()
        self.test.foo = self.Test2()

    def test_dotted_getattr(self):
        """Test dotted_getattr with a valid path."""
        attr = utils.dotted_getattr(self, 'test.foo.bar')
        self.assertEqual(attr, 1)

    def test_invalid_path(self):
        """Test dotted_getattr with an invalid path."""
        with self.assertRaises(AttributeError):
            _ = utils.dotted_getattr(self, 'test.foo.baz')


class SafeShlexSplitTests(unittest.TestCase):

    """Test safe_shlex_split."""

    def test_normal(self):
        """Test safe_shlex_split with a simple string."""
        items = utils.safe_shlex_split('one two')
        self.assertEqual(items, ['one', 'two'])

    def test_quoted(self):
        """Test safe_shlex_split with a normally quoted string."""
        items = utils.safe_shlex_split('one "two three" four')
        self.assertEqual(items, ['one', 'two three', 'four'])

    def test_escaped(self):
        """Test safe_shlex_split with a normal escaped string."""
        items = utils.safe_shlex_split(r'one "two\" three" four')
        self.assertEqual(items, ['one', 'two" three', 'four'])

    def test_unbalanced_quotes(self):
        """Test safe_shlex_split with unbalanded quotes."""
        items = utils.safe_shlex_split(r'one "two three')
        self.assertEqual(items, ['one', 'two three'])

    def test_unfinished_escape(self):
        """Test safe_shlex_split with an unfinished escape."""
        items = utils.safe_shlex_split('one\\')
        self.assertEqual(items, ['one\\'])

    def test_both(self):
        """Test safe_shlex_split with an unfinished escape and quotes.."""
        items = utils.safe_shlex_split('one "two\\')
        self.assertEqual(items, ['one', 'two\\'])


class GetStandardDirLinuxTests(unittest.TestCase):

    """Tests for get_standard_dir under Linux.

    Attributes:
        temp_dir: A temporary directory.
        app: The QCoreApplication used.
    """

    def setUp(self):
        self.temp_dir = mkdtemp()
        self.app = QCoreApplication([])
        self.app.setApplicationName('qutebrowser')

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_data_explicit(self):
        """Test data dir with XDG_DATA_HOME explicitely set."""
        with environ_set_temp('XDG_DATA_HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.DataLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_config_explicit(self):
        """Test config dir with XDG_CONFIG_HOME explicitely set."""
        with environ_set_temp('XDG_CONFIG_HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.ConfigLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_cache_explicit(self):
        """Test cache dir with XDG_CACHE_HOME explicitely set."""
        with environ_set_temp('XDG_CACHE_HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.CacheLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_data(self):
        """Test data dir with XDG_DATA_HOME not set."""
        with environ_set_temp('HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.DataLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.local',
                                                   'share', 'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_config(self):
        """Test config dir with XDG_CONFIG_HOME not set."""
        with environ_set_temp('HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(
                QStandardPaths.ConfigLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.config',
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_cache(self):
        """Test cache dir with XDG_CACHE_HOME not set."""
        with environ_set_temp('HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.CacheLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.cache',
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    def tearDown(self):
        self.app.quit()
        shutil.rmtree(self.temp_dir)


class GetStandardDirWindowsTests(unittest.TestCase):

    """Tests for get_standard_dir under Windows.

    Attributes:
        app: The QCoreApplication used.
    """

    def setUp(self):
        self.app = QCoreApplication([])
        # We can't store the files in a temp dir, so we don't chose qutebrowser
        self.app.setApplicationName('qutebrowser_test')

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_data(self):
        """Test data dir."""
        cur_dir = utils.get_standard_dir(QStandardPaths.DataLocation)
        self.assertEqual(cur_dir.split(os.sep)[-1], 'qutebrowser_test',
                         cur_dir)
        self.assertTrue(os.path.exists(cur_dir))
        # We clean up here as we don't dare to clean up if the path doesn't end
        # with qutebrowser_test - it could be *anywhere* after all.
        shutil.rmtree(cur_dir)

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_config(self):
        """Test config dir."""
        cur_dir = utils.get_standard_dir(QStandardPaths.ConfigLocation)
        self.assertEqual(cur_dir.split(os.sep)[-1], 'qutebrowser_test',
                         cur_dir)
        self.assertTrue(os.path.exists(cur_dir))
        # We clean up here as we don't dare to clean up if the path doesn't end
        # with qutebrowser_test - it could be *anywhere* after all.
        shutil.rmtree(cur_dir)

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_cache(self):
        """Test cache dir."""
        cur_dir = utils.get_standard_dir(QStandardPaths.CacheLocation)
        self.assertEqual(cur_dir.split(os.sep)[-2:],
                         ['qutebrowser_test', 'cache'], cur_dir)
        self.assertTrue(os.path.exists(cur_dir))
        # We clean up here as we don't dare to clean up if the path doesn't end
        # with qutebrowser_test - it could be *anywhere* after all.
        shutil.rmtree(cur_dir)

    def tearDown(self):
        self.app.quit()


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
        with self.assertRaises(QtValueError):
            utils.interpolate_color(Color(), self.white, 0)

    def test_invalid_end(self):
        """Test an invalid end color."""
        with self.assertRaises(QtValueError):
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
            self.assertEqual(utils.format_seconds(seconds), out, seconds)


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
            self.assertEqual(utils.format_size(size), out, size)

    def test_suffix(self):
        """Test the suffix option."""
        for size, out in self.TESTS:
            self.assertEqual(utils.format_size(size, suffix='B'), out + 'B',
                             size)

    def test_base(self):
        """Test with an alternative base."""
        kilo_tests = [(999, '999.00'), (1000, '1.00k'), (1010, '1.01k')]
        for size, out in kilo_tests:
            self.assertEqual(utils.format_size(size, base=1000), out, size)


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
        """Test keyeevent when only control is pressed."""
        evt = fake_keyevent(key=Qt.Key_Control, modifiers=Qt.ControlModifier)
        self.assertIsNone(utils.keyevent_to_string(evt))

    def test_only_hyper_l(self):
        """Test keyeevent when only Hyper_L is pressed."""
        evt = fake_keyevent(key=Qt.Key_Hyper_L, modifiers=Qt.MetaModifier)
        self.assertIsNone(utils.keyevent_to_string(evt))

    def test_only_key(self):
        """Test with a simple key pressed."""
        evt = fake_keyevent(key=Qt.Key_A)
        self.assertEqual(utils.keyevent_to_string(evt), 'A')

    def test_key_and_modifier(self):
        """Test with key and modifier pressed."""
        evt = fake_keyevent(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        self.assertEqual(utils.keyevent_to_string(evt), 'Ctrl+A')

    def test_key_and_modifiers(self):
        """Test with key and multiple modifier pressed."""
        evt = fake_keyevent(key=Qt.Key_A,
                            modifiers=(Qt.ControlModifier | Qt.AltModifier |
                                       Qt.MetaModifier | Qt.ShiftModifier))
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
            self.assertEqual(utils.normalize_keystr(orig), repl, orig)


if __name__ == '__main__':
    unittest.main()
