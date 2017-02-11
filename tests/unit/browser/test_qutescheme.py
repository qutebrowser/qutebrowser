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
import collections

from PyQt5.QtCore import QUrl
import pytest

from qutebrowser.browser import history, qutescheme
from qutebrowser.utils import objreg


Dates = collections.namedtuple('Dates', ['yesterday', 'today', 'tomorrow'])


class TestHistoryHandler:

    """Test the qute://history endpoint."""

    @pytest.fixture
    def dates(self):
        one_day = datetime.timedelta(days=1)
        today = datetime.datetime.today()
        tomorrow = today + one_day
        yesterday = today - one_day
        return Dates(yesterday, today, tomorrow)

    @pytest.fixture
    def entries(self, dates):
        today = history.Entry(atime=str(dates.today.timestamp()),
            url=QUrl('www.today.com'), title='today')
        tomorrow = history.Entry(atime=str(dates.tomorrow.timestamp()),
            url=QUrl('www.tomorrow.com'), title='tomorrow')
        yesterday = history.Entry(atime=str(dates.yesterday.timestamp()),
            url=QUrl('www.yesterday.com'), title='yesterday')
        return Dates(yesterday, today, tomorrow)

    @pytest.fixture
    def fake_web_history(self, fake_save_manager, tmpdir):
        """Create a fake web-history and register it into objreg."""
        web_history = history.WebHistory(tmpdir.dirname, 'fake-history')
        objreg.register('web-history', web_history)
        yield web_history
        objreg.delete('web-history')

    @pytest.fixture(autouse=True)
    def fake_history(self, fake_web_history, entries):
        """Create fake history for three different days."""
        fake_web_history._add_entry(entries.yesterday)
        fake_web_history._add_entry(entries.today)
        fake_web_history._add_entry(entries.tomorrow)
        fake_web_history.save()

    def test_history_without_query(self):
        """Ensure qute://history shows today's history without any query."""
        _mimetype, data = qutescheme.qute_history(QUrl("qute://history"))
        key = "<span class=\"date\">{}</span>".format(
            datetime.date.today().strftime("%a, %d %B %Y"))
        assert key in data

    def test_history_with_bad_query(self):
        """Ensure qute://history shows today's history with bad query."""
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

    def test_history_yesterday(self, dates):
        """Ensure qute://history shows history for yesterday."""
        url = QUrl("qute://history?date=" +
                dates.yesterday.strftime("%Y-%m-%d"))
        _mimetype, data = qutescheme.qute_history(url)
        assert "today" not in data
        assert "tomorrow" not in data
        assert "yesterday" in data

    def test_history_tomorrow(self, dates):
        """Ensure qute://history shows history for tomorrow."""
        url = QUrl("qute://history?date=" +
                dates.tomorrow.strftime("%Y-%m-%d"))
        _mimetype, data = qutescheme.qute_history(url)
        assert "today" not in data
        assert "tomorrow" in data
        assert "yesterday" not in data

    def test_no_next_link_to_future(self, dates):
        """Ensure there's no next link pointing to the future."""
        url = QUrl("qute://history")
        _mimetype, data = qutescheme.qute_history(url)
        assert "Next" not in data

        url = QUrl("qute://history?date=" +
                dates.tomorrow.strftime("%Y-%m-%d"))
        _mimetype, data = qutescheme.qute_history(url)
        assert "Next" not in data

    def test_qute_history_benchmark(self, dates, entries, fake_web_history,
                                    benchmark):
        for i in range(100000):
            entry = history.Entry(
                atime=str(dates.yesterday.timestamp()),
                url=QUrl('www.yesterday.com/{}'.format(i)),
                title='yesterday')
            fake_web_history._add_entry(entry)
        fake_web_history._add_entry(entries.today)
        fake_web_history._add_entry(entries.tomorrow)

        url = QUrl("qute://history")
        _mimetype, data = benchmark(qutescheme.qute_history, url)

        assert "today" in data
        assert "tomorrow" not in data
        assert "yesterday" not in data
