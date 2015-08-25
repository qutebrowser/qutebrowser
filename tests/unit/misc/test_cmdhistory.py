# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Alexander Cogneau (acogneau) <alexander.cogneau@gmail.com>:
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

"""Tests for misc.History."""

import pytest

from qutebrowser.misc.cmdhistory import (History, HistoryEmptyError,
                                         HistoryEndReachedError)


HISTORY = ['first', 'second', 'third', 'fourth', 'fifth']

CONFIG_NOT_PRIVATE = {'general': {'private-browsing': False}}
CONFIG_PRIVATE = {'general': {'private-browsing': True}}


class TestConstructor:

    """Tests for the constructor."""

    def test_no_history(self):
        hist = History()
        # .history should equal []
        assert len(hist.history) == 0

    def test_history(self):
        hist = History(history=HISTORY)
        assert hist.history == HISTORY


class TestCommandHistory:

    """Tests for Command History."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hist = History(history=HISTORY)

    def test_is_browsing(self):
        """Test is_browsing()."""

        self.hist._tmphist = None
        assert not self.hist.is_browsing()

        self.hist._tmphist = HISTORY
        assert self.hist.is_browsing()

    def test_start_stop(self):
        """Test the start/stop."""

        # We can use is_browsing() because it is tested above
        assert not self.hist.is_browsing()
        self.hist.start('s')
        assert self.hist.is_browsing()
        self.hist.stop()
        assert not self.hist.is_browsing()

    def test_start_with_text(self):
        """Test start with given 'text'."""
        self.hist.start('f')
        assert 'first' in self.hist._tmphist
        assert 'fourth' in self.hist._tmphist
        assert 'second' not in self.hist._tmphist

    def test_start_no_text(self):
        """Test start with no given text."""
        self.hist.start('')

        # There is probably a better way for NeighbourList?
        for i in self.hist._tmphist:
            assert i in HISTORY

        for i in HISTORY:
            assert i in self.hist._tmphist

    def test_start_no_items(self):
        """Test start with no matching text."""
        with pytest.raises(HistoryEmptyError) as excinfo:
            self.hist.start('k')
        assert str(excinfo.value) == "History is empty."
        assert not self.hist._tmphist

    def test_get_item(self):
        """Test __get_item__."""
        for i in range(0, len(HISTORY)):
            assert self.hist[i] == HISTORY[i]

    def test_not_browsing_error(self):
        """Test that next/previtem throws a ValueError"""
        with pytest.raises(ValueError) as error1:
            self.hist.nextitem()
        assert str(error1.value) == "Currently not browsing history"

        with pytest.raises(ValueError) as error2:
            self.hist.previtem()
        assert str(error2.value) == "Currently not browsing history"

    def return_item(self):
        return 'item'

    def test_nextitem_single(self):
        """Test nextitem() with valid input."""
        self.hist.start('f')
        self.hist._tmphist.nextitem = self.return_item
        assert self.hist.nextitem() == 'item'

    def test_previtem_single(self):
        """Test previtem() with valid input."""
        self.hist.start('f')
        self.hist._tmphist.previtem = self.return_item
        assert self.hist.previtem() == 'item'

    def test_nextitem_previtem_chain(self):
        """Test a combination of nextitem and previtem statements"""
        assert self.hist.start('f') == 'fifth'
        assert self.hist.previtem() == 'fourth'
        assert self.hist.previtem() == 'first'
        assert self.hist.nextitem() == 'fourth'

    def raise_index_error(self):
        raise IndexError()

    def test_nextitem_index_error(self):
        """"Test nextitem() when _tmphist raises an IndexError"""
        self.hist.start('f')
        self.hist._tmphist.nextitem = self.raise_index_error
        with pytest.raises(HistoryEndReachedError) as excinfo:
            self.hist.nextitem()
        assert str(excinfo.value) == "History end reached"

    def test_previtem_index_error(self):
        """"Test previtem() when _tmphist raises an IndexError"""
        self.hist.start('f')
        self.hist._tmphist.previtem = self.raise_index_error
        with pytest.raises(HistoryEndReachedError) as excinfo:
            self.hist.previtem()
        assert str(excinfo.value) == "History end reached"

    def test_append_private_mode(self, monkeypatch, config_stub):
        """Test append in private mode."""
        self.hist.handle_private_mode = True
        # We want general.private-browsing set to True
        config_stub.data = CONFIG_PRIVATE
        monkeypatch.setattr('qutebrowser.misc.cmdhistory.config',
                            config_stub)
        self.hist.append('new item')
        assert self.hist.history == HISTORY

    def test_append(self, monkeypatch, config_stub):
        """Test append outside private mode."""

        # Private mode is disabled (general.private-browsing is set to False)
        config_stub.data = CONFIG_NOT_PRIVATE
        monkeypatch.setattr('qutebrowser.misc.cmdhistory.config',
                            config_stub)
        self.hist.append('new item')
        assert 'new item' in self.hist.history
        self.hist.history.remove('new item')
        assert self.hist.history == HISTORY

    def test_append_empty_history(self, monkeypatch, config_stub):
        """Test append when .history is empty."""
        # Disable private mode
        config_stub.data = CONFIG_NOT_PRIVATE
        monkeypatch.setattr('qutebrowser.misc.cmdhistory.config',
                            config_stub)
        self.hist.history = []
        self.hist.append('item')
        assert self.hist[0] == 'item'

    def test_append_double(self, monkeypatch, config_stub):
        # Disable private mode
        config_stub.data = CONFIG_NOT_PRIVATE
        monkeypatch.setattr('qutebrowser.misc.cmdhistory.config',
                            config_stub)
        self.hist.append('fifth')
        # assert that the new 'fifth' is not added
        assert self.hist.history[-1] == 'fifth'
        assert self.hist.history[-2] == 'fourth'
