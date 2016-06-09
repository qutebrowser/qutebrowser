# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for the global page history."""

import pytest

from PyQt5.QtCore import QUrl

from qutebrowser.browser import history


@pytest.fixture()
def hist(tmpdir, fake_save_manager, config_stub):
    config_stub.data = {'general': {'private-browsing': False}}
    return history.WebHistory(hist_dir=str(tmpdir), hist_name='history')


def test_init(hist, fake_save_manager):
    assert fake_save_manager.add_saveable.called


def test_adding_item_during_async_read(qtbot, hist):
    """Check what happens when adding URL while reading the history."""
    with qtbot.assertNotEmitted(hist.add_completion_item), \
            qtbot.assertNotEmitted(hist.item_added):
        hist.add_url(QUrl('http://www.example.com/'))

    with qtbot.waitSignals([hist.add_completion_item,
                            hist.async_read_done]):
        list(hist.async_read())

    assert not hist._temp_history

    urls = [item.url for item in hist.history_dict.values()]
    assert urls == [QUrl('http://www.example.com/')]


def test_private_browsing(qtbot, tmpdir, fake_save_manager, config_stub):
    """Make sure no data is saved at all with private browsing."""
    config_stub.data = {'general': {'private-browsing': True}}
    private_hist = history.WebHistory(hist_dir=str(tmpdir),
                                      hist_name='history')

    # Before initial read
    with qtbot.assertNotEmitted(private_hist.add_completion_item), \
            qtbot.assertNotEmitted(private_hist.item_added):
        private_hist.add_url(QUrl('http://www.example.com/'))
    assert not private_hist._temp_history

    # read
    with qtbot.assertNotEmitted(private_hist.add_completion_item), \
            qtbot.assertNotEmitted(private_hist.item_added):
        with qtbot.waitSignals([private_hist.async_read_done]):
            list(private_hist.async_read())

    # after read
    with qtbot.assertNotEmitted(private_hist.add_completion_item), \
            qtbot.assertNotEmitted(private_hist.item_added):
        private_hist.add_url(QUrl('http://www.example.com/'))

    assert not private_hist._temp_history
    assert not private_hist._new_history
    assert not private_hist.history_dict


@pytest.mark.parametrize('line, expected', [
    (
        # old format without title
        '12345 http://example.com/',
        history.Entry(atime=12345, url=QUrl('http://example.com/'), title='',)
    ),
    (
        # new format with title
        '12345 http://example.com/ this is a title',
        history.Entry(atime=12345, url=QUrl('http://example.com/'),
                      title='this is a title')
    ),
    (
        # weird NUL bytes
        '\x0012345 http://example.com/',
        history.Entry(atime=12345, url=QUrl('http://example.com/'), title=''),
    ),
])
def test_entry_parse_valid(line, expected):
    entry = history.Entry.from_str(line)
    assert entry == expected


@pytest.mark.parametrize('line', [
    '12345',  # one field
    '12345 ::',  # invalid URL
    'xyz http://www.example.com/',  # invalid timestamp
])
def test_entry_parse_invalid(line):
    with pytest.raises(ValueError):
        history.Entry.from_str(line)
