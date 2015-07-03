# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for webelement.tabhistory."""

from PyQt5.QtCore import QUrl, QPoint
import pytest

from qutebrowser.browser import tabhistory
from qutebrowser.browser.tabhistory import TabHistoryItem as Item
from qutebrowser.utils import qtutils


class TestSerializeHistory:

    """Tests for serialize()."""

    ITEMS = [
        Item(QUrl('https://www.heise.de/'), QUrl('http://www.heise.de/'),
             'heise'),
        Item(QUrl('http://example.com/%E2%80%A6'),
             QUrl('http://example.com/%E2%80%A6'), 'percent', active=True),
        Item(QUrl('http://example.com/?foo=bar'),
             QUrl('http://original.url.example.com/'), 'arg',
             user_data={'foo': 23, 'bar': 42}),
        # From https://github.com/OtterBrowser/otter-browser/issues/709#issuecomment-74749471
        Item(
            QUrl('http://github.com/OtterBrowser/24/134/2344/otter-browser/'
                 'issues/709/'),
            QUrl('http://github.com/OtterBrowser/24/134/2344/otter-browser/'
                 'issues/709/'),
            'Page not found | github',
            user_data={'zoom': 149, 'scroll-pos': QPoint(0, 0)}),
        Item(
            QUrl('https://mail.google.com/mail/u/0/#label/some+label/'
                 '234lkjsd0932lkjf884jqwerdf4'),
            QUrl('https://mail.google.com/mail/u/0/#label/some+label/'
                 '234lkjsd0932lkjf884jqwerdf4'),
            '"some label" - email@gmail.com - Gmail"',
            user_data={'zoom': 120, 'scroll-pos': QPoint(0, 0)}),
    ]

    @pytest.fixture(autouse=True)
    def setup(self, webpage):
        self.page = webpage
        self.history = self.page.history()
        assert self.history.count() == 0

        stream, _data, self.user_data = tabhistory.serialize(self.ITEMS)
        qtutils.deserialize_stream(stream, self.history)

    def test_count(self):
        """Check if the history's count was loaded correctly."""
        assert self.history.count() == len(self.ITEMS)

    @pytest.mark.parametrize('i', range(len(ITEMS)))
    def test_valid(self, i):
        """Check if all items are valid."""
        assert self.history.itemAt(i).isValid()

    @pytest.mark.parametrize('i', range(len(ITEMS)))
    def test_no_userdata(self, i):
        """Check if all items have no user data."""
        assert self.history.itemAt(i).userData() is None

    def test_userdata(self):
        """Check if all user data has been restored to self.user_data."""
        userdata_items = [item.user_data for item in self.ITEMS]
        assert userdata_items == self.user_data

    def test_currentitem(self):
        """Check if the current item index was loaded correctly."""
        assert self.history.currentItemIndex() == 1

    @pytest.mark.parametrize('i, item', enumerate(ITEMS))
    def test_urls(self, i, item):
        """Check if the URLs were loaded correctly."""
        assert self.history.itemAt(i).url() == item.url

    @pytest.mark.parametrize('i, item', enumerate(ITEMS))
    def test_original_urls(self, i, item):
        """Check if the original URLs were loaded correctly."""
        assert self.history.itemAt(i).originalUrl() == item.original_url

    @pytest.mark.parametrize('i, item', enumerate(ITEMS))
    def test_titles(self, i, item):
        """Check if the titles were loaded correctly."""
        assert self.history.itemAt(i).title() == item.title


class TestSerializeHistorySpecial:

    """Tests for serialize() without items set up in setup."""

    @pytest.fixture(autouse=True)
    def setup(self, webpage):
        """Set up the initial QWebPage for each test."""
        self.page = webpage
        self.history = self.page.history()
        assert self.history.count() == 0

    def test_no_active_item(self):
        """Check tabhistory.serialize with no active item."""
        items = [Item(QUrl(), QUrl(), '')]
        with pytest.raises(ValueError):
            tabhistory.serialize(items)

    def test_two_active_items(self):
        """Check tabhistory.serialize with two active items."""
        items = [Item(QUrl(), QUrl(), '', active=True),
                 Item(QUrl(), QUrl(), ''),
                 Item(QUrl(), QUrl(), '', active=True)]
        with pytest.raises(ValueError):
            tabhistory.serialize(items)

    def test_empty(self):
        """Check tabhistory.serialize with no items."""
        items = []
        stream, _data, user_data = tabhistory.serialize(items)
        qtutils.deserialize_stream(stream, self.history)
        assert self.history.count() == 0
        assert self.history.currentItemIndex() == 0
        assert not user_data
