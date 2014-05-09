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
import unittest
import os.path
import subprocess
from tempfile import mkdtemp
from unittest import TestCase

from PyQt5.QtCore import QStandardPaths, QCoreApplication

import qutebrowser.utils.misc as utils
from qutebrowser.test.helpers import environ_set_temp


class ReadFileTests(TestCase):

    """Test read_file."""

    def test_readfile(self):
        content = utils.read_file(os.path.join('test', 'testfile'))
        self.assertEqual(content.splitlines()[0], "Hello World!")


class DottedGetattrTests(TestCase):

    """Test dotted_getattr."""

    class Test:

        foo = None

    class Test2:

        bar = 1

    def setUp(self):
        self.test = self.Test()
        self.test.foo = self.Test2()

    def test_dotted_getattr(self):
        attr = utils.dotted_getattr(self, 'test.foo.bar')
        self.assertEqual(attr, 1)

    def test_invalid_path(self):
        with self.assertRaises(AttributeError):
            _ = utils.dotted_getattr(self, 'test.foo.baz')


class SafeShlexSplitTests(TestCase):

    """Test safe_shlex_split."""

    def test_normal(self):
        items = utils.safe_shlex_split('one two')
        self.assertEqual(items, ['one', 'two'])

    def test_quoted(self):
        items = utils.safe_shlex_split('one "two three" four')
        self.assertEqual(items, ['one', 'two three', 'four'])

    def test_escaped(self):
        items = utils.safe_shlex_split(r'one "two\" three" four')
        self.assertEqual(items, ['one', 'two" three', 'four'])

    def test_unbalanced_quotes(self):
        items = utils.safe_shlex_split(r'one "two three')
        self.assertEqual(items, ['one', 'two three'])

    def test_unfinished_escape(self):
        items = utils.safe_shlex_split('one\\')
        self.assertEqual(items, ['one\\'])

    def test_both(self):
        items = utils.safe_shlex_split('one "two\\')
        self.assertEqual(items, ['one', 'two\\'])


class ShellEscapeTests(TestCase):

    TEXTS_LINUX = [
        ('', "''"),
        ('foo%bar+baz', 'foo%bar+baz'),
        ('foo$bar', "'foo$bar'"),
        ("$'b", """'$'"'"'b'"""),
    ]

    TEXTS_WINDOWS = [
        ('', '""'),
        ('foo*bar?baz', 'foo*bar?baz'),
        ("a&b|c^d<e>f%", "a^&b^|c^^d^<e^>f^%"),
        ('foo"bar', 'foo"""bar'),
    ]

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

    def setUp(self):
        self.temp_dir = mkdtemp()
        self.app = QCoreApplication([])
        self.app.setApplicationName('qutebrowser')

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_data_explicit(self):
        with environ_set_temp('XDG_DATA_HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.DataLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_config_explicit(self):
        with environ_set_temp('XDG_CONFIG_HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.ConfigLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_cache_explicit(self):
        with environ_set_temp('XDG_CACHE_HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.CacheLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_data(self):
        with environ_set_temp('HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.DataLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.local',
                                                   'share', 'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_config(self):
        with environ_set_temp('HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(
                QStandardPaths.ConfigLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.config',
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_cache(self):
        with environ_set_temp('HOME', self.temp_dir):
            cur_dir = utils.get_standard_dir(QStandardPaths.CacheLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.cache',
                                                   'qutebrowser'))
            self.assertTrue(os.path.exists(cur_dir))

    def tearDown(self):
        self.app.quit()
        shutil.rmtree(self.temp_dir)


class GetStandardDirWindowsTests(TestCase):

    def setUp(self):
        self.app = QCoreApplication([])
        # We can't store the files in a temp dir, so we don't chose qutebrowser
        self.app.setApplicationName('qutebrowser_test')

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_data(self):
        cur_dir = utils.get_standard_dir(QStandardPaths.DataLocation)
        self.assertEqual(cur_dir.split(os.sep)[-1], 'qutebrowser_test',
                         cur_dir)
        self.assertTrue(os.path.exists(cur_dir))
        # We clean up here as we don't dare to clean up if the path doesn't end
        # with qutebrowser_test - it could be *anywhere* after all.
        shutil.rmtree(cur_dir)

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_config(self):
        cur_dir = utils.get_standard_dir(QStandardPaths.ConfigLocation)
        self.assertEqual(cur_dir.split(os.sep)[-1], 'qutebrowser_test',
                         cur_dir)
        self.assertTrue(os.path.exists(cur_dir))
        # We clean up here as we don't dare to clean up if the path doesn't end
        # with qutebrowser_test - it could be *anywhere* after all.
        shutil.rmtree(cur_dir)

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_cache(self):
        cur_dir = utils.get_standard_dir(QStandardPaths.CacheLocation)
        self.assertEqual(cur_dir.split(os.sep)[-2:],
                         ['qutebrowser_test', 'cache'], cur_dir)
        self.assertTrue(os.path.exists(cur_dir))
        # We clean up here as we don't dare to clean up if the path doesn't end
        # with qutebrowser_test - it could be *anywhere* after all.
        shutil.rmtree(cur_dir)

    def tearDown(self):
        self.app.quit()


if __name__ == '__main__':
    unittest.main()
