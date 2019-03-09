# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019 Jay Kamat <jaygkamat@gmail.com>
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

"""Tests for qutebrowser.misc.pool."""

from unittest import mock
import pytest

from qutebrowser.misc import pool


@pytest.mark.parametrize('should_cleanup', [True, False])
def test_basic_usage(should_cleanup):
    obj = {1: 2}
    sentenel = 10
    mock_constructor = mock.Mock(spec=[], return_value=obj)

    if should_cleanup:
        mock_cleanup = mock.Mock(spec=[])
    else:
        mock_cleanup = None

    p = pool.Pool(mock_constructor, 5, mock_cleanup)

    aquired_obj = p.acquire(sentenel)
    assert aquired_obj is obj

    p.release(aquired_obj)
    if should_cleanup:
        mock_cleanup.assert_called_once_with(obj)


def test_max_logic():
    iterations = 1000
    min_size = 5
    p = pool.Pool(lambda: {1: 2}, min_size)
    aquired_arr = []

    for _ in range(iterations):
        aquired_arr.append(p.acquire())

    assert p._active_objects == iterations

    for item in aquired_arr:
        p.release(item)

    assert len(p._pool) == iterations

    # stress _housekeeping to see if we clean anything up prematurely (if we
    # have a bug)
    for _ in range(p.MAX_SIZE_WINDOW + 1):
        p._housekeeping()

    assert len(p._pool) == iterations

    # Now, toggle many times to see if we go down to min
    for _ in range(p.MAX_SIZE_WINDOW - 1):
        p.release(p.acquire())

    assert len(p._pool) == iterations

    # last one!
    p.release(p.acquire())

    assert len(p._pool) == min_size
