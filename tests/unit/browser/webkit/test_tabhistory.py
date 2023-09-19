# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for webelement.tabhistory."""

import dataclasses
from typing import Any

import pytest
pytest.importorskip('qutebrowser.qt.webkit')
from qutebrowser.qt.core import QUrl, QPoint
# pylint: disable=no-name-in-module
from qutebrowser.qt.webkit import QWebHistory
# pylint: enable=no-name-in-module

from qutebrowser.browser.webkit import tabhistory
from qutebrowser.misc.sessions import TabHistoryItem as Item
from qutebrowser.utils import qtutils


pytestmark = pytest.mark.qt_log_ignore('QIODevice::read.*: device not open')


ITEMS = [
    Item(QUrl('https://www.heise.de/'), 'heise'),
    Item(QUrl('about:blank'), 'blank', active=True),
    Item(QUrl('http://example.com/%E2%80%A6'), 'percent'),
    Item(QUrl('http://example.com/?foo=bar'), 'arg',
         original_url=QUrl('http://original.url.example.com/'),
         user_data={'foo': 23, 'bar': 42}),
    # From https://github.com/OtterBrowser/otter-browser/issues/709#issuecomment-74749471
    Item(QUrl('http://github.com/OtterBrowser/24/134/2344/otter-browser/'
              'issues/709/'),
         'Page not found | github',
         user_data={'zoom': 149, 'scroll-pos': QPoint(0, 0)}),
    Item(QUrl('https://mail.google.com/mail/u/0/#label/some+label/'
              '234lkjsd0932lkjf884jqwerdf4'),
         '"some label" - email@gmail.com - Gmail"',
         user_data={'zoom': 120, 'scroll-pos': QPoint(0, 0)}),
]


@dataclasses.dataclass
class Objects:

    history: QWebHistory
    user_data: Any


@pytest.fixture
def empty_history(webpage):
    """Fixture providing an empty QWebHistory."""
    hist = webpage.history()
    assert hist.count() == 0
    return hist


@pytest.fixture
def objects(empty_history):
    """Fixture providing a history (and userdata) filled with example data."""
    stream, _data, user_data = tabhistory.serialize(ITEMS)
    qtutils.deserialize_stream(stream, empty_history)
    return Objects(history=empty_history, user_data=user_data)


def test_count(objects):
    """Check if the history's count was loaded correctly."""
    assert objects.history.count() == len(ITEMS)


@pytest.mark.parametrize('i', range(len(ITEMS)))
def test_valid(objects, i):
    """Check if all items are valid."""
    assert objects.history.itemAt(i).isValid()


@pytest.mark.parametrize('i', range(len(ITEMS)))
def test_no_userdata(objects, i):
    """Check if all items have no user data."""
    assert objects.history.itemAt(i).userData() is None


def test_userdata(objects):
    """Check if all user data has been restored to user_data."""
    userdata_items = [item.user_data for item in ITEMS]
    assert userdata_items == objects.user_data


def test_currentitem(objects):
    """Check if the current item index was loaded correctly."""
    assert objects.history.currentItemIndex() == 1


@pytest.mark.parametrize('i, item', enumerate(ITEMS))
def test_urls(objects, i, item):
    """Check if the URLs were loaded correctly."""
    assert objects.history.itemAt(i).url() == item.url


@pytest.mark.parametrize('i, item', enumerate(ITEMS))
def test_original_urls(objects, i, item):
    """Check if the original URLs were loaded correctly."""
    assert objects.history.itemAt(i).originalUrl() == item.original_url


@pytest.mark.parametrize('i, item', enumerate(ITEMS))
def test_titles(objects, i, item):
    """Check if the titles were loaded correctly."""
    assert objects.history.itemAt(i).title() == item.title


def test_no_active_item():
    """Check tabhistory.serialize with no active item."""
    items = [Item(QUrl(), '')]
    with pytest.raises(ValueError):
        tabhistory.serialize(items)


def test_two_active_items():
    """Check tabhistory.serialize with two active items."""
    items = [Item(QUrl(), '', active=True),
             Item(QUrl(), ''),
             Item(QUrl(), '', active=True)]
    with pytest.raises(ValueError):
        tabhistory.serialize(items)


def test_empty(empty_history):
    """Check tabhistory.serialize with no items."""
    items = []
    stream, _data, user_data = tabhistory.serialize(items)
    qtutils.deserialize_stream(stream, empty_history)
    assert empty_history.count() == 0
    assert empty_history.currentItemIndex() == 0
    assert not user_data
