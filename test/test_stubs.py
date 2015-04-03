# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Test test stubs."""

import unittest
from unittest import mock

from qutebrowser.test import stubs


class TestFakeTimer(unittest.TestCase):

    """Test FakeTimer."""

    def setUp(self):
        self.timer = stubs.FakeTimer()

    def test_timeout(self):
        """Test whether timeout calls the functions."""
        func = mock.Mock()
        func2 = mock.Mock()
        self.timer.timeout.connect(func)
        self.timer.timeout.connect(func2)
        self.assertFalse(func.called)
        self.assertFalse(func2.called)
        self.timer.timeout.emit()
        func.assert_called_once_with()
        func2.assert_called_once_with()

    def test_disconnect_all(self):
        """Test disconnect without arguments."""
        func = mock.Mock()
        self.timer.timeout.connect(func)
        self.timer.timeout.disconnect()
        self.timer.timeout.emit()
        self.assertFalse(func.called)

    def test_disconnect_one(self):
        """Test disconnect with a single argument."""
        func = mock.Mock()
        self.timer.timeout.connect(func)
        self.timer.timeout.disconnect(func)
        self.timer.timeout.emit()
        self.assertFalse(func.called)

    def test_disconnect_all_invalid(self):
        """Test disconnecting with no connections."""
        with self.assertRaises(TypeError):
            self.timer.timeout.disconnect()

    def test_disconnect_one_invalid(self):
        """Test disconnecting with an invalid connection."""
        func1 = mock.Mock()
        func2 = mock.Mock()
        self.timer.timeout.connect(func1)
        with self.assertRaises(TypeError):
            self.timer.timeout.disconnect(func2)
        self.assertFalse(func1.called)
        self.assertFalse(func2.called)
        self.timer.timeout.emit()
        func1.assert_called_once_with()

    def test_singleshot(self):
        """Test setting singleShot."""
        self.assertFalse(self.timer.singleShot())
        self.timer.setSingleShot(True)
        self.assertTrue(self.timer.singleShot())
        self.timer.start()
        self.assertTrue(self.timer.isActive())
        self.timer.timeout.emit()
        self.assertFalse(self.timer.isActive())

    def test_active(self):
        """Test isActive."""
        self.assertFalse(self.timer.isActive())
        self.timer.start()
        self.assertTrue(self.timer.isActive())
        self.timer.stop()
        self.assertFalse(self.timer.isActive())

    def test_interval(self):
        """Test setting an interval."""
        self.assertEqual(self.timer.interval(), 0)
        self.timer.setInterval(1000)
        self.assertEqual(self.timer.interval(), 1000)


if __name__ == '__main__':
    unittest.main()
