# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2018 Imran Sobir
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
            entry = {"atime": str(entry_atime),
                     "url": QUrl("www.x.com/" + str(i)),
                     "title": "Page " + str(i)}
            items.insert(0, entry)

        return items

    @pytest.fixture
    def fake_web_history(self, fake_save_manager, tmpdir, init_sql):
        """Create a fake web-history and register it into objreg."""
        web_history = history.WebHistory()
        objreg.register('web-history', web_history)
        yield web_history
        objreg.delete('web-history')

    @pytest.fixture(autouse=True)
    def fake_history(self, fake_web_history, fake_args, entries):
        """Create fake history."""
        fake_args.debug_flags = []
        for item in entries:
            fake_web_history.add_url(**item)

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

        assert len(items) == expected_item_count

        # test times
        end_time = start_time - 24*60*60
        for item in items:
            assert item['time'] <= start_time
            assert item['time'] > end_time

    def test_qute_history_benchmark(self, fake_web_history, benchmark, now):
        r = range(100000)
        entries = {
            'atime': [int(now - t) for t in r],
            'url': ['www.x.com/{}'.format(t) for t in r],
            'title': ['x at {}'.format(t) for t in r],
            'redirect': [False for _ in r],
        }

        fake_web_history.insert_batch(entries)
        url = QUrl("qute://history/data?start_time={}".format(now))
        _mimetype, data = benchmark(qutescheme.qute_history, url)
        assert len(json.loads(data)) > 1


class TestHelpHandler:

    """Tests for qute://help."""

    @pytest.fixture
    def data_patcher(self, monkeypatch):
        def _patch(path, data):
            def _read_file(name, binary=False):
                assert path == name
                if binary:
                    return data
                return data.decode('utf-8')

            monkeypatch.setattr(qutescheme.utils, 'read_file', _read_file)
        return _patch

    def test_unknown_file_type(self, data_patcher):
        data_patcher('html/doc/foo.bin', b'\xff')
        mimetype, data = qutescheme.qute_help(QUrl('qute://help/foo.bin'))
        assert mimetype == 'application/octet-stream'
        assert data == b'\xff'
