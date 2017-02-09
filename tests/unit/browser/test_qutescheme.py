# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Imran Sobir
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

import datetime

from PyQt5.QtCore import QUrl
import pytest

from qutebrowser.browser import history, qutescheme
from qutebrowser.utils import objreg


class TestHistoryHandler:

    """Test the qute://history endpoint."""

    @pytest.fixture
    def fake_web_history(self, fake_save_manager, tmpdir):
        """Create a fake web-history and register it into objreg."""
        fake_web_history = history.WebHistory(tmpdir.dirname, 'fake-history')
        objreg.register('web-history', fake_web_history)

        yield fake_web_history

        objreg.delete('web-history')

    @pytest.fixture(autouse=True)
    def generate_fake_history(self, fake_web_history):
        """Create fake history for three different days."""
        one_day = datetime.timedelta(days=1)
        self.curr_date = datetime.datetime.today()
        self.next_date = self.curr_date + one_day
        self.prev_date = self.curr_date - one_day

        today = history.Entry(atime=str(self.curr_date.timestamp()),
            url=QUrl('www.today.com'), title='today')
        tomorrow = history.Entry(atime=str(self.next_date.timestamp()),
            url=QUrl('www.tomorrow.com'), title='tomorrow')
        yesterday = history.Entry(atime=str(self.prev_date.timestamp()),
            url=QUrl('www.yesterday.com'), title='yesterday')

        fake_web_history = objreg.get('web-history')
        fake_web_history._add_entry(today)
        fake_web_history._add_entry(tomorrow)
        fake_web_history._add_entry(yesterday)
        fake_web_history.save()

    def test_history_without_query(self):
        """Ensure qute://history shows today's history when it has no query."""
        _mimetype, data = qutescheme.qute_history(QUrl("qute://history"))
        key = "<span class=\"date\">{}</span>".format(
            datetime.date.today().strftime("%a, %d %B %Y"))
        assert key in data

    def test_history_with_bad_query(self):
        """Ensure qute://history shows today's history when given bad query."""
        url = QUrl("qute://history?date=204-blaah")
        _mimetype, data = qutescheme.qute_history(url)
        key = "<span class=\"date\">{}</span>".format(
            datetime.date.today().strftime("%a, %d %B %Y"))
        assert key in data

    def test_history_today(self):
        """Ensure qute://history shows history for today."""
        url = QUrl("qute://history")
        _mimetype, data = qutescheme.qute_history(url)
        assert "today" in data
        assert "tomorrow" not in data
        assert "yesterday" not in data

    def test_history_yesterday(self):
        """Ensure qute://history shows history for yesterday."""
        url = QUrl("qute://history?date=" + self.prev_date.strftime("%Y-%m-%d"))
        _mimetype, data = qutescheme.qute_history(url)
        assert "today" not in data
        assert "tomorrow" not in data
        assert "yesterday" in data

    def test_history_tomorrow(self):
        """Ensure qute://history shows history for tomorrow."""
        url = QUrl("qute://history?date=" + self.next_date.strftime("%Y-%m-%d"))
        _mimetype, data = qutescheme.qute_history(url)
        assert "today" not in data
        assert "tomorrow" in data
        assert "yesterday" not in data
