# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The-Compiler) <me@the-compiler.org>
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

"""Tests for misc.cmdhistory.History."""

import pytest

import qutebrowser.browser.history

from unittest import mock

from qutebrowser.misc import cmdhistory
from qutebrowser.browser.history import WebHistory

from qutebrowser.browser import cookies
from qutebrowser.utils import objreg
from qutebrowser.misc import lineparser, savemanager

# autouse fixtures (so no need to pass to tests)
# @pytest.yield_fixture(autouse=True)

HISTORY = ['first', 'second', 'third', 'fourth', 'fifth']

@pytest.yield_fixture(autouse=True)
def fake_save_manager():
    """Create a mock of save-manager and register it into objreg."""
    fake_save_manager = mock.Mock(spec=savemanager.SaveManager)
    objreg.register('save-manager', fake_save_manager)
    yield
    objreg.delete('save-manager')


def test_async_read(qapp):
    wb = WebHistory()
    wb._lineparser = LineparserSaveStub()
    wb.async_read()
    rp = wb.__repr__()
    assert rp  == '<qutebrowser.browser.history.WebHistory length=0>'


class LineparserSaveStub(lineparser.BaseLineParser):
    """A stub for LineParser's save()
    Attributes:
        data: The data before the write
        saved: The .data before save()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved = []
        self.data = []

    def save(self):
        self.saved = self.data

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, key):
        return self.data[key]


