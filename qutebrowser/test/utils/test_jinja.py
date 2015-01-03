# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.utils.jinja."""

import os.path
import unittest
import unittest.mock

from qutebrowser.utils import jinja


def _read_file(path):
    """Mocked utils.read_file."""
    if path == os.path.join('html', 'test.html'):
        return """Hello {{var}}"""
    else:
        raise ValueError("Invalid path {}!".format(path))


@unittest.mock.patch('qutebrowser.utils.jinja.utils.read_file')
class JinjaTests(unittest.TestCase):

    """Tests for getting template via jinja."""

    def test_simple_template(self, readfile_mock):
        """Test with a simple template."""
        readfile_mock.side_effect = _read_file
        template = jinja.env.get_template('test.html')
        data = template.render(var='World')  # pylint: disable=maybe-no-member
        self.assertEqual(data, "Hello World")

    def test_utf8(self, readfile_mock):
        """Test rendering with an UTF8 template.

        This was an attempt to get a failing test case for #127 but it seems
        the issue is elsewhere.

        https://github.com/The-Compiler/qutebrowser/issues/127
        """
        readfile_mock.side_effect = _read_file
        template = jinja.env.get_template('test.html')
        data = template.render(var='\u2603')  # pylint: disable=maybe-no-member
        self.assertEqual(data, "Hello \u2603")


if __name__ == '__main__':
    unittest.main()
