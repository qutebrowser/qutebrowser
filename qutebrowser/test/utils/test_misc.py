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

# pylint: disable=missing-docstring,blacklisted-name,protected-access

"""Tests for qutebrowser.utils.misc."""

import os
import sys
import shutil
import argparse
import unittest
import os.path
import subprocess
from tempfile import mkdtemp
from unittest import TestCase

from PyQt5.QtCore import QStandardPaths, QCoreApplication
from PyQt5.QtGui import QColor

import qutebrowser.utils.misc as utils
from qutebrowser.test.helpers import environ_set_temp


class ElidingTests(TestCase):

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


class CheckOverflowTests(TestCase):

    """Test check_overflow.

    Class attributes:
        INT32_MIN: Minimum valid value for a signed int32.
        INT32_MAX: Maximum valid value for a signed int32.
        INT64_MIN: Minimum valid value for a signed int64.
        INT64_MAX: Maximum valid value for a signed int64.
        GOOD_VALUES: A dict of types mapped to a list of good values.
        BAD_VALUES: A dict of types mapped to a list of bad values.
    """

    INT32_MIN = -(2 ** 31)
    INT32_MAX = 2 ** 31 - 1
    INT64_MIN = -(2 ** 63)
    INT64_MAX = 2 ** 63 - 1

    GOOD_VALUES = {
        'int': [-1, 0, 1, 23.42, INT32_MIN, INT32_MAX],
        'int64': [-1, 0, 1, 23.42, INT64_MIN, INT64_MAX],
    }

    BAD_VALUES = {
        'int': [(INT32_MIN - 1, INT32_MIN),
                (INT32_MAX + 1, INT32_MAX),
                (float(INT32_MAX + 1), INT32_MAX)],
        'int64': [(INT64_MIN - 1, INT64_MIN),
                  (INT64_MAX + 1, INT64_MAX),
                  (float(INT64_MAX + 1), INT64_MAX)],
    }

    def test_good_values(self):
        """Test values which are inside bounds."""
        for ctype, vals in self.GOOD_VALUES.items():
            for val in vals:
                utils.check_overflow(val, ctype)

    def test_bad_values_fatal(self):
        """Test values which are outside bounds with fatal=True."""
        for ctype, vals in self.BAD_VALUES.items():
            for (val, _) in vals:
                with self.assertRaises(OverflowError, msg=ctype):
                    utils.check_overflow(val, ctype)

    def test_bad_values_nonfatal(self):
        """Test values which are outside bounds with fatal=False."""
        for ctype, vals in self.BAD_VALUES.items():
            for (val, replacement) in vals:
                newval = utils.check_overflow(val, ctype, fatal=False)
                self.assertEqual(newval, replacement,
                                 "{}: {}".format(ctype, val))


class ReadFileTests(TestCase):

    """Test read_file."""

    def test_readfile(self):
        """Read a testfile."""
        content = utils.read_file(os.path.join('test', 'testfile'))
        self.assertEqual(content.splitlines()[0], "Hello World!")


class DottedGetattrTests(TestCase):

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


class SafeShlexSplitTests(TestCase):

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


class ShellEscapeTests(TestCase):

    """Tests for shell_escape.

    Class attributes:
        TEXTS_LINUX: A list of (input, output) of expected texts for Linux.
        TEXTS_WINDOWS: A list of (input, output) of expected texts for Windows.

    Attributes:
        platform: The saved sys.platform value.
    """

    TEXTS_LINUX = (
        ('', "''"),
        ('foo%bar+baz', 'foo%bar+baz'),
        ('foo$bar', "'foo$bar'"),
        ("$'b", """'$'"'"'b'"""),
    )

    TEXTS_WINDOWS = (
        ('', '""'),
        ('foo*bar?baz', 'foo*bar?baz'),
        ("a&b|c^d<e>f%", "a^&b^|c^^d^<e^>f^%"),
        ('foo"bar', 'foo"""bar'),
    )

    def setUp(self):
        self.platform = sys.platform

    def test_fake_linux(self):
        """Fake test which simply checks if the escaped string looks right."""
        sys.platform = 'linux'
        for (orig, escaped) in self.TEXTS_LINUX:
            self.assertEqual(utils.shell_escape(orig), escaped)

    def test_fake_windows(self):
        """Fake test which simply checks if the escaped string looks right."""
        sys.platform = 'win32'
        for (orig, escaped) in self.TEXTS_WINDOWS:
            self.assertEqual(utils.shell_escape(orig), escaped)

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_real_linux(self):
        """Real test which prints an escaped string via python."""
        for (orig, _escaped) in self.TEXTS_LINUX:
            cmd = ("python -c 'import sys; print(sys.argv[1], end=\"\")' "
                   "{}".format(utils.shell_escape(orig)))
            out = subprocess.check_output(cmd, shell=True).decode('ASCII')
            self.assertEqual(out, orig, cmd)

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_real_windows(self):
        """Real test which prints an escaped string via python."""
        for (orig, _escaped) in self.TEXTS_WINDOWS:
            cmd = ('python -c "import sys; print(sys.argv[1], end=\'\')" '
                   '{}'.format(utils.shell_escape(orig)))
            out = subprocess.check_output(cmd, shell=True).decode('ASCII')
            self.assertEqual(out, orig, cmd)

    def tearDown(self):
        sys.platform = self.platform


class GetStandardDirLinuxTests(TestCase):

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


class GetStandardDirWindowsTests(TestCase):

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


class GetQtArgsTests(TestCase):

    """Tests for get_qt_args."""

    def setUp(self):
        self.parser = argparse.ArgumentParser()

    def _namespace(self, cmdline, flags=None, args=None):
        """Get an argparse namespace object based on arguments given.

        Args:
            cmdline: The given commandline.
            flags: A list of strings (argument names) for flags without an
                   argument.
            args: A list of arguemnt names for flags with an argument.
        """
        if flags is not None:
            for e in flags:
                self.parser.add_argument(e, action='store_true')
        if args is not None:
            for e in args:
                self.parser.add_argument(e, nargs=1)
        return self.parser.parse_args(cmdline)

    def test_no_qt_args(self):
        """Test commandline with no Qt arguments given."""
        ns = self._namespace(['--foo'], flags=['--foo'])
        self.assertEqual(utils.get_qt_args(ns), [sys.argv[0]])

    def test_qt_flag(self):
        """Test commandline with a Qt flag."""
        ns = self._namespace(['--foo', '--qt-reverse', '--bar'],
                             flags=['--foo', '--qt-reverse', '--bar'])
        self.assertEqual(utils.get_qt_args(ns), [sys.argv[0], '-reverse'])

    def test_qt_arg(self):
        """Test commandline with a Qt argument."""
        ns = self._namespace(['--qt-stylesheet', 'foobar'],
                             args=['--qt-stylesheet'])
        self.assertEqual(utils.get_qt_args(ns), [sys.argv[0], '-stylesheet',
                                                 'foobar'])

    def test_qt_both(self):
        """Test commandline with a Qt argument and flag."""
        ns = self._namespace(['--qt-stylesheet', 'foobar', '--qt-reverse'],
                             flags=['--qt-reverse'], args=['--qt-stylesheet'])
        self.assertEqual(utils.get_qt_args(ns), [sys.argv[0],
                                                 '-stylesheet', 'foobar',
                                                 '-reverse'])

    def test_qt_unknown(self):
        """Test commandline with unknown Qt argument."""
        ns = self._namespace(['--qt-foo'], flags=['--qt-foo'])
        self.assertEqual(utils.get_qt_args(ns), [sys.argv[0]])


class InterpolateColorTests(TestCase):

    """Tests for interpolate_color.

    Attributes:
        white: The QColor white as a valid QColor for tests.
        white: The QColor black as a valid QColor for tests.
    """

    def setUp(self):
        self.white = QColor('white')
        self.black = QColor('black')

    def test_invalid_start(self):
        """Test an invalid start color."""
        with self.assertRaises(ValueError):
            utils.interpolate_color(QColor(), self.white, 0)

    def test_invalid_end(self):
        """Test an invalid end color."""
        with self.assertRaises(ValueError):
            utils.interpolate_color(self.white, QColor(), 0)

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
        self.assertEqual(white, self.white)
        self.assertEqual(black, self.black)

    def test_valid_percentages_hsv(self):
        """Test 0% and 100% in the HSV colorspace."""
        white = utils.interpolate_color(self.white, self.black, 0, QColor.Hsv)
        black = utils.interpolate_color(self.white, self.black, 100,
                                        QColor.Hsv)
        self.assertEqual(white, self.white)
        self.assertEqual(black, self.black)

    def test_valid_percentages_hsl(self):
        """Test 0% and 100% in the HSL colorspace."""
        white = utils.interpolate_color(self.white, self.black, 0, QColor.Hsl)
        black = utils.interpolate_color(self.white, self.black, 100,
                                        QColor.Hsl)
        self.assertEqual(white, self.white)
        self.assertEqual(black, self.black)

    def test_interpolation_rgb(self):
        """Test an interpolation in the RGB colorspace."""
        color = utils.interpolate_color(QColor(0, 40, 100), QColor(0, 20, 200),
                                        50, QColor.Rgb)
        self.assertEqual(color, QColor(0, 30, 150))

    def test_interpolation_hsv(self):
        """Test an interpolation in the HSV colorspace."""
        start = QColor()
        stop = QColor()
        start.setHsv(0, 40, 100)
        stop.setHsv(0, 20, 200)
        color = utils.interpolate_color(start, stop, 50, QColor.Hsv)
        expected = QColor()
        expected.setHsv(0, 30, 150)
        self.assertEqual(color, expected)

    def test_interpolation_hsl(self):
        """Test an interpolation in the HSL colorspace."""
        start = QColor()
        stop = QColor()
        start.setHsl(0, 40, 100)
        stop.setHsl(0, 20, 200)
        color = utils.interpolate_color(start, stop, 50, QColor.Hsl)
        expected = QColor()
        expected.setHsl(0, 30, 150)
        self.assertEqual(color, expected)


if __name__ == '__main__':
    unittest.main()
