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

"""Tests for qutebrowser.utils.standarddir."""

import os
import os.path
import sys
import shutil
import unittest
import tempfile

from PyQt5.QtCore import QStandardPaths, QCoreApplication

from qutebrowser.utils import standarddir
from qutebrowser.test import helpers


class GetStandardDirLinuxTests(unittest.TestCase):

    """Tests for standarddir.get under Linux.

    Attributes:
        temp_dir: A temporary directory.
        app: The QCoreApplication used.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.app = QCoreApplication([])
        self.app.setApplicationName('qutebrowser')

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_data_explicit(self):
        """Test data dir with XDG_DATA_HOME explicitely set."""
        with helpers.environ_set_temp('XDG_DATA_HOME', self.temp_dir):
            cur_dir = standarddir.get(QStandardPaths.DataLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_config_explicit(self):
        """Test config dir with XDG_CONFIG_HOME explicitely set."""
        with helpers.environ_set_temp('XDG_CONFIG_HOME', self.temp_dir):
            cur_dir = standarddir.get(QStandardPaths.ConfigLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_cache_explicit(self):
        """Test cache dir with XDG_CACHE_HOME explicitely set."""
        with helpers.environ_set_temp('XDG_CACHE_HOME', self.temp_dir):
            cur_dir = standarddir.get(QStandardPaths.CacheLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir,
                                                   'qutebrowser'))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_data(self):
        """Test data dir with XDG_DATA_HOME not set."""
        with helpers.environ_set_temp('HOME', self.temp_dir):
            cur_dir = standarddir.get(QStandardPaths.DataLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.local',
                                                   'share', 'qutebrowser'))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_config(self):
        """Test config dir with XDG_CONFIG_HOME not set."""
        with helpers.environ_set_temp('HOME', self.temp_dir):
            cur_dir = standarddir.get(
                QStandardPaths.ConfigLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.config',
                                                   'qutebrowser'))

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux")
    def test_cache(self):
        """Test cache dir with XDG_CACHE_HOME not set."""
        with helpers.environ_set_temp('HOME', self.temp_dir):
            cur_dir = standarddir.get(QStandardPaths.CacheLocation)
            self.assertEqual(cur_dir, os.path.join(self.temp_dir, '.cache',
                                                   'qutebrowser'))

    def tearDown(self):
        self.app.quit()
        shutil.rmtree(self.temp_dir)


class GetStandardDirWindowsTests(unittest.TestCase):

    """Tests for standarddir.get under Windows.

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
        cur_dir = standarddir.get(QStandardPaths.DataLocation)
        self.assertEqual(cur_dir.split(os.sep)[-2:],
                         ['qutebrowser_test', 'data'], cur_dir)

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_config(self):
        """Test config dir."""
        cur_dir = standarddir.get(QStandardPaths.ConfigLocation)
        self.assertEqual(cur_dir.split(os.sep)[-1], 'qutebrowser_test',
                         cur_dir)

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_cache(self):
        """Test cache dir."""
        cur_dir = standarddir.get(QStandardPaths.CacheLocation)
        self.assertEqual(cur_dir.split(os.sep)[-2:],
                         ['qutebrowser_test', 'cache'], cur_dir)

    def tearDown(self):
        self.app.quit()
