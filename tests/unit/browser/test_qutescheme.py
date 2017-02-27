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

import json
import time

from PyQt5.QtCore import QUrl
import pytest

from qutebrowser.browser import history, qutescheme
from qutebrowser.utils import objreg


class TestHistoryHandler:

    """Test the qute://history endpoint."""

    @pytest.fixture
    def entries(self):
        """Create fake history entries."""
        # create 12 history items spaced 6 hours apart, starting from now
        entry_count = 12
        interval = 6 * 60 * 60
        self.now = time.time()

        items = []
        for i in range(entry_count):
            entry_atime = int(self.now - i * interval)
            entry = history.Entry(atime=str(entry_atime),
                url=QUrl("www.x.com/" + str(i)), title="Page " + str(i))
            items.insert(0, entry)

        return items

    @pytest.fixture
    def fake_web_history(self, fake_save_manager, tmpdir):
        """Create a fake web-history and register it into objreg."""
        web_history = history.WebHistory(tmpdir.dirname, 'fake-history')
        objreg.register('web-history', web_history)
        yield web_history
        objreg.delete('web-history')

    @pytest.fixture(autouse=True)
    def fake_history(self, fake_web_history, entries):
        """Create fake history."""
        for item in entries:
            fake_web_history._add_entry(item)
        fake_web_history.save()

    @pytest.mark.parametrize("start_time_offset, expected_item_count", [
        (0, 5),
        (24*60*60, 5),
        (48*60*60, 5),
        (72*60*60, 1)
    ])
    def test_qutehistory_data(self, start_time_offset, expected_item_count):
        """Ensure qute://history/data returns correct items."""
        start_time = int(self.now) - start_time_offset
        url = QUrl("qute://history/data?start_time=" + str(start_time))
        _mimetype, data = qutescheme.qute_history(url)
        items = json.loads(data)

        assert len(items) == expected_item_count

        # test times
        end_time = start_time - 24*60*60
        for item in items[:expected_item_count-1]:
            assert item['time'] <= start_time
            assert item['time'] > end_time

    @pytest.mark.parametrize("start_time_offset, next_time", [
        (0, 24*60*60),
        (24*60*60, 48*60*60),
        (48*60*60, -1),
        (72*60*60, -1)
    ])
    def test_qutehistory_next(self, start_time_offset, next_time):
        """Ensure qute://history/data returns correct items."""
        start_time = int(self.now) - start_time_offset
        url = QUrl("qute://history/data?start_time=" + str(start_time))
        _mimetype, data = qutescheme.qute_history(url)
        items = json.loads(data)

        if next_time == -1:
            assert items[-1]["next"] == -1
        else:
            assert items[-1]["next"] == int(self.now) - next_time

    def test_qute_history_benchmark(self, fake_web_history, benchmark):
        for t in range(100000):  # one history per second
            entry = history.Entry(
                atime=str(self.now - t),
                url=QUrl('www.x.com/{}'.format(t)),
                title='x at {}'.format(t))
            fake_web_history._add_entry(entry)

        url = QUrl("qute://history/data?start_time={}".format(self.now))
        _mimetype, _data = benchmark(qutescheme.qute_history, url)
