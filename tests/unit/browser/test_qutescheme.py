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
import os
import time

from PyQt5.QtCore import QUrl
import pytest

from qutebrowser.browser import history, qutescheme
from qutebrowser.utils import objreg


class TestJavascriptHandler:

    """Test the qute://javascript endpoint."""

    # Tuples of fake JS files and their content.
    js_files = [
        ('foo.js', "var a = 'foo';"),
        ('bar.js', "var a = 'bar';"),
    ]

    @pytest.fixture(autouse=True)
    def patch_read_file(self, monkeypatch):
        """Patch utils.read_file to return few fake JS files."""
        def _read_file(path, binary=False):
            """Faked utils.read_file."""
            assert not binary
            for filename, content in self.js_files:
                if path == os.path.join('javascript', filename):
                    return content
            raise OSError("File not found {}!".format(path))

        monkeypatch.setattr('qutebrowser.utils.utils.read_file', _read_file)

    @pytest.mark.parametrize("filename, content", js_files)
    def test_qutejavascript(self, filename, content):
        url = QUrl("qute://javascript/{}".format(filename))
        _mimetype, data = qutescheme.qute_javascript(url)

        assert data == content

    def test_qutejavascript_404(self):
        url = QUrl("qute://javascript/404.js")

        with pytest.raises(qutescheme.QuteSchemeOSError):
            qutescheme.data_for_url(url)

    def test_qutejavascript_empty_query(self):
        url = QUrl("qute://javascript")

        with pytest.raises(qutescheme.QuteSchemeError):
            qutescheme.qute_javascript(url)


class TestHistoryHandler:

    """Test the qute://history endpoint."""

    @pytest.fixture(scope="module")
    def now(self):
        return int(time.time())

    @pytest.fixture
    def entries(self, now):
        """Create fake history entries."""
        # create 12 history items spaced 6 hours apart, starting from now
        entry_count = 12
        interval = 6 * 60 * 60

        items = []
        for i in range(entry_count):
            entry_atime = now - i * interval
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
        (0, 4),
        (24*60*60, 4),
        (48*60*60, 4),
        (72*60*60, 0)
    ])
    def test_qutehistory_data(self, start_time_offset, expected_item_count,
            now):
        """Ensure qute://history/data returns correct items."""
        start_time = now - start_time_offset
        url = QUrl("qute://history/data?start_time=" + str(start_time))
        _mimetype, data = qutescheme.qute_history(url)
        items = json.loads(data)
        items = [item for item in items if 'time' in item]  # skip 'next' item

        assert len(items) == expected_item_count

        # test times
        end_time = start_time - 24*60*60
        for item in items:
            assert item['time'] <= start_time * 1000
            assert item['time'] > end_time * 1000

    @pytest.mark.parametrize("start_time_offset, next_time", [
        (0, 24*60*60),
        (24*60*60, 48*60*60),
        (48*60*60, -1),
        (72*60*60, -1)
    ])
    def test_qutehistory_next(self, start_time_offset, next_time, now):
        """Ensure qute://history/data returns correct items."""
        start_time = now - start_time_offset
        url = QUrl("qute://history/data?start_time=" + str(start_time))
        _mimetype, data = qutescheme.qute_history(url)
        items = json.loads(data)
        items = [item for item in items if 'next' in item]  # 'next' items
        assert len(items) == 1

        if next_time == -1:
            assert items[0]["next"] == -1
        else:
            assert items[0]["next"] == now - next_time

    def test_qute_history_benchmark(self, fake_web_history, benchmark, now):
        # items must be earliest-first to ensure history is sorted properly
        for t in range(100000, 0, -1):  # one history per second
            entry = history.Entry(
                atime=str(now - t),
                url=QUrl('www.x.com/{}'.format(t)),
                title='x at {}'.format(t))
            fake_web_history._add_entry(entry)

        url = QUrl("qute://history/data?start_time={}".format(now))
        _mimetype, data = benchmark(qutescheme.qute_history, url)
        assert len(json.loads(data)) > 1
