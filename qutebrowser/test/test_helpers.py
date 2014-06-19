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

# pylint: disable=missing-docstring

"""Test test helpers."""

import os
from unittest import TestCase

from qutebrowser.test.helpers import environ_set_temp


class TestEnvironSetTemp(TestCase):

    """Test the environ_set_temp helper."""

    def test_environ_set(self):
        """Test environ_set_temp with something which was set already."""
        os.environ['QUTEBROWSER_ENVIRON_TEST'] = 'oldval'
        with environ_set_temp('QUTEBROWSER_ENVIRON_TEST', 'newval'):
            self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST'], 'newval')
        self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST'], 'oldval')

    def test_environ_unset(self):
        """Test environ_set_temp with something which wasn't set yet."""
        with environ_set_temp('QUTEBROWSER_ENVIRON_TEST', 'newval'):
            self.assertEqual(os.environ['QUTEBROWSER_ENVIRON_TEST'], 'newval')
        self.assertNotIn('QUTEBROWSER_ENVIRON_TEST', os.environ)

    def tearDown(self):
        if 'QUTEBROWSER_ENVIRON_TEST' in os.environ:
            # if some test failed
            del os.environ['QUTEBROWSER_ENVIRON_TEST']
