# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for browser.signalfilter."""

import collections
import logging

import pytest
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject

from qutebrowser.browser import signalfilter
from qutebrowser.utils import objreg


class FakeTabbedBrowser:

    def __init__(self):
        self.index_of = None
        self.current_index = None

    def indexOf(self, _tab):
        if self.index_of is None:
            raise ValueError("indexOf got called with index_of None!")
        elif self.index_of is RuntimeError:
            raise RuntimeError
        else:
            return self.index_of

    def currentIndex(self):
        if self.current_index is None:
            raise ValueError("currentIndex got called with current_index "
                             "None!")
        return self.current_index


class Signaller(QObject):

    signal = pyqtSignal(str)
    link_hovered = pyqtSignal(str)

    filtered_signal = pyqtSignal(str)
    cur_link_hovered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filtered_signal_arg = None
        self.filtered_signal.connect(self.filtered_signal_slot)

    @pyqtSlot(str)
    def filtered_signal_slot(self, s):
        self.filtered_signal_arg = s


Objects = collections.namedtuple('Objects', 'signal_filter, signaller')


@pytest.fixture
def objects():
    signal_filter = signalfilter.SignalFilter(0)
    tab = None
    signaller = Signaller()
    signaller.signal.connect(
        signal_filter.create(signaller.filtered_signal, tab))
    signaller.link_hovered.connect(
        signal_filter.create(signaller.cur_link_hovered, tab))
    return Objects(signal_filter=signal_filter, signaller=signaller)


@pytest.yield_fixture
def tabbed_browser(win_registry):
    tb = FakeTabbedBrowser()
    objreg.register('tabbed-browser', tb, scope='window', window=0)
    yield tb
    objreg.delete('tabbed-browser', scope='window', window=0)


@pytest.mark.parametrize('index_of, emitted', [(0, True), (1, False)])
def test_filtering(objects, tabbed_browser, index_of, emitted):
    tabbed_browser.current_index = 0
    tabbed_browser.index_of = index_of
    objects.signaller.signal.emit('foo')
    if emitted:
        assert objects.signaller.filtered_signal_arg == 'foo'
    else:
        assert objects.signaller.filtered_signal_arg is None


@pytest.mark.parametrize('index_of, verb', [(0, 'emitting'), (1, 'ignoring')])
def test_logging(caplog, objects, tabbed_browser, index_of, verb):
    tabbed_browser.current_index = 0
    tabbed_browser.index_of = index_of

    with caplog.at_level(logging.DEBUG, logger='signals'):
        objects.signaller.signal.emit('foo')

    assert len(caplog.records) == 1
    expected_msg = "{}: filtered_signal('foo') (tab {})".format(verb, index_of)
    assert caplog.records[0].msg == expected_msg


@pytest.mark.parametrize('index_of', [0, 1])
def test_no_logging(caplog, objects, tabbed_browser, index_of):
    tabbed_browser.current_index = 0
    tabbed_browser.index_of = index_of

    with caplog.at_level(logging.DEBUG, logger='signals'):
        objects.signaller.link_hovered.emit('foo')

    assert not caplog.records


def test_runtime_error(objects, tabbed_browser):
    """Test that there's no crash if indexOf() raises RuntimeError."""
    tabbed_browser.current_index = 0
    tabbed_browser.index_of = RuntimeError
    objects.signaller.signal.emit('foo')
    assert objects.signaller.filtered_signal_arg is None
