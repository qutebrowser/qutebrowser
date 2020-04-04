# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import logging

import attr
import pytest
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject

from qutebrowser.browser import signalfilter


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


@attr.s
class Objects:

    signal_filter = attr.ib()
    signaller = attr.ib()


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


@pytest.mark.parametrize('index_of, emitted', [(0, True), (1, False)])
def test_filtering(objects, tabbed_browser_stubs, index_of, emitted):
    browser = tabbed_browser_stubs[0]
    browser.widget.current_index = 0
    browser.widget.index_of = index_of
    objects.signaller.signal.emit('foo')
    if emitted:
        assert objects.signaller.filtered_signal_arg == 'foo'
    else:
        assert objects.signaller.filtered_signal_arg is None


@pytest.mark.parametrize('index_of, verb', [(0, 'emitting'), (1, 'ignoring')])
def test_logging(caplog, objects, tabbed_browser_stubs, index_of, verb):
    browser = tabbed_browser_stubs[0]
    browser.widget.current_index = 0
    browser.widget.index_of = index_of

    with caplog.at_level(logging.DEBUG, logger='signals'):
        objects.signaller.signal.emit('foo')

    expected_msg = "{}: filtered_signal('foo') (tab {})".format(verb, index_of)
    assert caplog.messages == [expected_msg]


@pytest.mark.parametrize('index_of', [0, 1])
def test_no_logging(caplog, objects, tabbed_browser_stubs, index_of):
    browser = tabbed_browser_stubs[0]
    browser.widget.current_index = 0
    browser.widget.index_of = index_of

    with caplog.at_level(logging.DEBUG, logger='signals'):
        objects.signaller.link_hovered.emit('foo')

    assert not caplog.records


def test_runtime_error(objects, tabbed_browser_stubs):
    """Test that there's no crash if indexOf() raises RuntimeError."""
    browser = tabbed_browser_stubs[0]
    browser.widget.current_index = 0
    browser.widget.index_of = RuntimeError
    objects.signaller.signal.emit('foo')
    assert objects.signaller.filtered_signal_arg is None
