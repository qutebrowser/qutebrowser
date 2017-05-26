# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.utils.typing."""

import pytest

from qutebrowser.utils import typing


@pytest.fixture
def pytyping():
    """A fixture to get the python 3.5+ typing module."""
    pytyping = pytest.importorskip('typing')
    return pytyping


class TestUnion:

    def test_python_subclass(self, pytyping):
        assert (type(pytyping.Union[str, int]) is  # flake8: disable=E721
                type(pytyping.Union))

    def test_qute_subclass(self):
        assert (type(typing.FakeUnion[str, int]) is  # flake8: disable=E721
                type(typing.FakeUnion))

    def test_python_params(self, pytyping):
        union = pytyping.Union[str, int]
        try:
            assert union.__union_params__ == (str, int)
        except AttributeError:
            assert union.__args__ == (str, int)

    def test_qute_params(self):
        union = typing.FakeUnion[str, int]
        try:
            assert union.__union_params__ == (str, int)
        except AttributeError:
            assert union.__args__ == (str, int)
