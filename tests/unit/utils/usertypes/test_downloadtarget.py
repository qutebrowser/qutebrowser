# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Daniel Schadt
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

"""Tests for the DownloadTarget class."""

from qutebrowser.utils import usertypes

import pytest


def test_base():
    with pytest.raises(NotImplementedError):
        usertypes.DownloadTarget()


def test_filename():
    target = usertypes.FileDownloadTarget("/foo/bar")
    assert target.filename == "/foo/bar"


def test_fileobj():
    fobj = object()
    target = usertypes.FileObjDownloadTarget(fobj)
    assert target.fileobj is fobj


def test_openfile():
    # Just make sure no error is raised, that should be enough.
    usertypes.OpenFileDownloadTarget()


@pytest.mark.parametrize('obj', [
    usertypes.FileDownloadTarget('foobar'),
    usertypes.FileObjDownloadTarget(None),
    usertypes.OpenFileDownloadTarget(),
])
def test_class_hierarchy(obj):
    assert isinstance(obj, usertypes.DownloadTarget)
