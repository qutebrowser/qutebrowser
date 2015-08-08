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

"""Tests for qutebrowser.browser.network.filescheme."""

import os

import pytest

from qutebrowser.browser.network.filescheme import get_file_list


@pytest.mark.parametrize('create_file, create_dir, filterfunc, expected', [
    (True, False, os.path.isfile, True),
    (True, False, os.path.isdir, False),

    (False, True, os.path.isfile, False),
    (False, True, os.path.isdir, True),

    (False, False, os.path.isfile, False),
    (False, False, os.path.isdir, False),
])
def test_get_file_list(tmpdir, create_file, create_dir, filterfunc, expected):
    """Test get_file_list."""
    path = tmpdir / 'foo'
    if create_file or create_dir:
        path.ensure(dir=create_dir)

    all_files = os.listdir(str(tmpdir))

    result = get_file_list(str(tmpdir), all_files, filterfunc)
    item = {'name': 'foo', 'absname': str(path)}
    assert (item in result) == expected
