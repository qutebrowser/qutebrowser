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


"""Test test helpers."""

import os
import unittest

from qutebrowser.test import helpers


class TestEnvironSetTemp(unittest.TestCase):

    """Test the environ_set_temp helper."""

    def test_environ_set(self):
        """Test environ_set_temp with something which was set already."""
        os.environ['QUTEBROWSER_ENVIRON_TEST'] = 'oldval'
        with helpers.environ_set_temp({'QUTEBROWSER_ENVIRON_TEST': 'newval'}):
            self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST'], 'newval')
        self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST'], 'oldval')

    def test_environ_unset(self):
        """Test environ_set_temp with something which wasn't set yet."""
        with helpers.environ_set_temp({'QUTEBROWSER_ENVIRON_TEST': 'newval'}):
            self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST'], 'newval')
        self.assertNotIn('QUTEBROWSER_ENVIRON_TEST', os.environ)

    def test_environ_multiple(self):
        """Test environ_set_temp with multiple values."""
        os.environ['QUTEBROWSER_ENVIRON_TEST_1'] = 'oldval_1'
        os.environ['QUTEBROWSER_ENVIRON_TEST_3'] = 'oldval_3'
        env = {
            'QUTEBROWSER_ENVIRON_TEST_1': 'newval_1',
            'QUTEBROWSER_ENVIRON_TEST_2': 'newval_2',
            'QUTEBROWSER_ENVIRON_TEST_3': None,
        }
        with helpers.environ_set_temp(env):
            self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST_1'],
                             'newval_1')
            self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST_2'],
                             'newval_2')
            self.assertNotIn('QUTEBROWSER_ENVIRON_TEST_3', os.environ)
        self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST_1'], 'oldval_1')
        self.assertNotIn('QUTEBROWSER_ENVIRON_TEST_2', os.environ)
        self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST_3'], 'oldval_3')

    def test_environ_none_set(self):
        """Test environ_set_temp with something which was set already."""
        os.environ['QUTEBROWSER_ENVIRON_TEST'] = 'oldval'
        with helpers.environ_set_temp({'QUTEBROWSER_ENVIRON_TEST': None}):
            self.assertNotIn('QUTEBROWSER_ENVIRON_TEST', os.environ)
        self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST'], 'oldval')

    def test_environ_none_unset(self):
        """Test environ_set_temp with something which wasn't set yet."""
        with helpers.environ_set_temp({'QUTEBROWSER_ENVIRON_TEST': None}):
            self.assertNotIn('QUTEBROWSER_ENVIRON_TEST', os.environ)
        self.assertNotIn('QUTEBROWSER_ENVIRON_TEST', os.environ)

    def tearDown(self):
        if 'QUTEBROWSER_ENVIRON_TEST' in os.environ:
            # if some test failed
            del os.environ['QUTEBROWSER_ENVIRON_TEST']

if __name__ == '__main__':
    unittest.main()
