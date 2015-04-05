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

from PyQt5.QtWidgets import QApplication
import pytest

from qutebrowser.utils import standarddir


@pytest.yield_fixture(autouse=True)
def change_qapp_name():
    """Change the name of the QApplication instance.

    This changes the applicationName for all tests in this module to
    "qutebrowser_test".
    """
    old_name = QApplication.instance().applicationName()
    QApplication.instance().setApplicationName('qutebrowser_test')
    yield
    QApplication.instance().setApplicationName(old_name)


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="requires Linux")
class TestGetStandardDirLinux:

    """Tests for standarddir under Linux."""

    def test_data_explicit(self, monkeypatch, tmpdir):
        """Test data dir with XDG_DATA_HOME explicitly set."""
        monkeypatch.setenv('XDG_DATA_HOME', str(tmpdir))
        standarddir.init(None)
        assert standarddir.data() == str(tmpdir / 'qutebrowser_test')

    def test_config_explicit(self, monkeypatch, tmpdir):
        """Test config dir with XDG_CONFIG_HOME explicitly set."""
        monkeypatch.setenv('XDG_CONFIG_HOME', str(tmpdir))
        standarddir.init(None)
        assert standarddir.config() == str(tmpdir / 'qutebrowser_test')

    def test_cache_explicit(self, monkeypatch, tmpdir):
        """Test cache dir with XDG_CACHE_HOME explicitly set."""
        monkeypatch.setenv('XDG_CACHE_HOME', str(tmpdir))
        standarddir.init(None)
        assert standarddir.cache() == str(tmpdir / 'qutebrowser_test')

    def test_data(self, monkeypatch, tmpdir):
        """Test data dir with XDG_DATA_HOME not set."""
        monkeypatch.setenv('HOME', str(tmpdir))
        monkeypatch.delenv('XDG_DATA_HOME', raising=False)
        standarddir.init(None)
        expected = tmpdir / '.local' / 'share' / 'qutebrowser_test'
        assert standarddir.data() == str(expected)

    def test_config(self, monkeypatch, tmpdir):
        """Test config dir with XDG_CONFIG_HOME not set."""
        monkeypatch.setenv('HOME', str(tmpdir))
        monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
        standarddir.init(None)
        expected = tmpdir / '.config' / 'qutebrowser_test'
        assert standarddir.config() == str(expected)

    def test_cache(self, monkeypatch, tmpdir):
        """Test cache dir with XDG_CACHE_HOME not set."""
        monkeypatch.setenv('HOME', str(tmpdir))
        monkeypatch.delenv('XDG_CACHE_HOME', raising=False)
        standarddir.init(None)
        expected = tmpdir / '.cache' / 'qutebrowser_test'
        assert standarddir.cache() == expected


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason="requires Windows")
class TestGetStandardDirWindows:

    """Tests for standarddir under Windows."""

    @pytest.fixture(autouse=True)
    def reset_standarddir(self):
        standarddir.init(None)

    def test_data(self):
        """Test data dir."""
        expected = ['qutebrowser_test', 'data']
        assert standarddir.data().split(os.sep)[-2:] == expected

    def test_config(self):
        """Test config dir."""
        assert standarddir.config().split(os.sep)[-1] == 'qutebrowser_test'

    def test_cache(self):
        """Test cache dir."""
        expected = ['qutebrowser_test', 'cache']
        assert standarddir.cache().split(os.sep)[-2:] == expected
