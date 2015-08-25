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

from qutebrowser.misc.cmdhistory import History, HistoryEmptyError


HISTORY = ['first', 'second', 'third', 'fourth', 'fifth']


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

    """Create a setup for inheritance"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hist = History(history=HISTORY)


class TestBrowsing(TestCommandHistory):

    """Tests for the history browsing."""

    def test_append_private_mode(self, monkeypatch):
        """Test append in private mode."""
        self.hist.handle_private_mode = True
        # We want general.private-browsing set to True
        monkeypatch.setattr('qutebrowser.config.config.get',
                            lambda s1, s2: True)
        self.hist.append('new item')
        assert self.hist.history == HISTORY

    def test_append(self, monkeypatch):
        """Test append outside private mode."""

        # Private mode is disabled (general.private-browsing is set to False)
        monkeypatch.setattr('qutebrowser.config.config.get',
                            lambda s1, s2: False)
        self.hist.append('new item')
        assert 'new item' in self.hist.history
        self.hist.history.remove('new item')
        assert self.hist.history == HISTORY

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
