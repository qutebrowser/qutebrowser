# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Antoni Boucher (antoyo) <bouanto@zoho.com>
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

"""Tests for qutebrowser.browser.dirbrowser."""

import os

from qutebrowser.browser.dirbrowser import get_file_list


class TestFileList:

    """Test file list."""

    def test_get_file_list(self):
        """Test get_file_list."""
        basedir = os.path.abspath('./qutebrowser/utils')
        all_files = os.listdir(basedir)
        result = get_file_list(basedir, all_files, os.path.isfile)
        assert {'name': 'testfile', 'absname': os.path.join(basedir,
                'testfile')} in result

        basedir = os.path.abspath('./qutebrowser/utils')
        all_files = os.listdir(basedir)
        result = get_file_list(basedir, all_files, os.path.isdir)
        print(result)
        assert {'name': 'testfile', 'absname': os.path.join(basedir,
                'testfile')} not in result

        basedir = os.path.abspath('./qutebrowser')
        all_files = os.listdir(basedir)
        result = get_file_list(basedir, all_files, os.path.isfile)
        assert ({'name': 'utils', 'absname': os.path.join(basedir, 'utils')}
                not in result)

        result = get_file_list(basedir, all_files, os.path.isdir)
        assert ({'name': 'utils', 'absname': os.path.join(basedir, 'utils')}
                in result)
