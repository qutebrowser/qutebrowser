# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Alexander Cogneau (acogneau) <alexander.cogneau@gmail.com>
# Copyright 2015-2016 Florian Bruhin (The-Compiler) <me@the-compiler.org>
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

from qutebrowser.misc import cmdhistory


HISTORY = ['first', 'second', 'third', 'fourth', 'fifth']

CONFIG_NOT_PRIVATE = {'general': {'private-browsing': False}}
CONFIG_PRIVATE = {'general': {'private-browsing': True}}


@pytest.fixture
def hist():
    return cmdhistory.History(history=HISTORY)


def test_no_history():
    hist = cmdhistory.History()
    assert hist.history == []


def test_history():
    hist = cmdhistory.History(history=HISTORY)
    assert hist.history == HISTORY


@pytest.mark.parametrize('tmphist, expected', [(None, False), (HISTORY, True)])
def test_is_browsing(hist, tmphist, expected):
    hist._tmphist = tmphist
    assert hist.is_browsing() == expected


def test_start_stop(hist):
    # We can use is_browsing() because it is tested above
    assert not hist.is_browsing()
    hist.start('s')
    assert hist.is_browsing()
    hist.stop()
    assert not hist.is_browsing()


def test_start_with_text(hist):
    """Test start with given 'text'."""
    hist.start('f')
    assert 'first' in hist._tmphist
    assert 'fourth' in hist._tmphist
    assert 'second' not in hist._tmphist


def test_start_no_text(hist):
    """Test start with no given text."""
    hist.start('')
    assert list(hist._tmphist) == HISTORY


def test_start_no_items(hist):
    """Test start with no matching text."""
    with pytest.raises(cmdhistory.HistoryEmptyError):
        hist.start('k')
    assert not hist._tmphist


def test_getitem(hist):
    """Test __getitem__."""
    for i in range(0, len(HISTORY)):
        assert hist[i] == HISTORY[i]


def test_setitem(hist):
    """Test __setitem__."""
    with pytest.raises(TypeError) as excinfo:
        hist[0] = 'foo'
    expected = "'History' object does not support item assignment"
    assert str(excinfo.value) == expected


def test_not_browsing_error(hist):
    """Test that next/previtem throws a ValueError."""
    with pytest.raises(ValueError) as error1:
        hist.nextitem()
    assert str(error1.value) == "Currently not browsing history"

    with pytest.raises(ValueError) as error2:
        hist.previtem()
    assert str(error2.value) == "Currently not browsing history"


def test_nextitem_single(hist, monkeypatch):
    """Test nextitem() with valid input."""
    hist.start('f')
    monkeypatch.setattr(hist._tmphist, 'nextitem', lambda: 'item')
    assert hist.nextitem() == 'item'


def test_previtem_single(hist, monkeypatch):
    """Test previtem() with valid input."""
    hist.start('f')
    monkeypatch.setattr(hist._tmphist, 'previtem', lambda: 'item')
    assert hist.previtem() == 'item'


def test_nextitem_previtem_chain(hist):
    """Test a combination of nextitem and previtem statements."""
    assert hist.start('f') == 'fifth'
    assert hist.previtem() == 'fourth'
    assert hist.previtem() == 'first'
    assert hist.nextitem() == 'fourth'


def test_nextitem_index_error(hist):
    """"Test nextitem() when _tmphist raises an IndexError."""
    hist.start('f')
    with pytest.raises(cmdhistory.HistoryEndReachedError):
        hist.nextitem()


def test_previtem_index_error(hist):
    """"Test previtem() when _tmphist raises an IndexError."""
    hist.start('f')
    with pytest.raises(cmdhistory.HistoryEndReachedError):
        for _ in range(10):
            hist.previtem()


def test_append_private_mode(hist, config_stub):
    """Test append in private mode."""
    hist.handle_private_mode = True
    # We want general.private-browsing set to True
    config_stub.data = CONFIG_PRIVATE
    hist.append('new item')
    assert hist.history == HISTORY


def test_append(hist, config_stub):
    """Test append outside private mode."""
    # Private mode is disabled (general.private-browsing is set to False)
    config_stub.data = CONFIG_NOT_PRIVATE
    hist.append('new item')
    assert 'new item' in hist.history
    hist.history.remove('new item')
    assert hist.history == HISTORY


def test_append_empty_history(hist, config_stub):
    """Test append when .history is empty."""
    # Disable private mode
    config_stub.data = CONFIG_NOT_PRIVATE
    hist.history = []
    hist.append('item')
    assert hist[0] == 'item'


def test_append_double(hist, config_stub):
    # Disable private mode
    config_stub.data = CONFIG_NOT_PRIVATE
    hist.append('fifth')
    # assert that the new 'fifth' is not added
    assert hist.history[-2:] == ['fourth', 'fifth']
