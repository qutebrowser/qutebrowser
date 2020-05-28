# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import logging

import py.path  # pylint: disable=no-name-in-module
from PyQt5.QtCore import QUrl, QUrlQuery
import pytest

from qutebrowser.browser import qutescheme, pdfjs, downloads


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

        with pytest.raises(qutescheme.SchemeOSError):
            qutescheme.data_for_url(url)

    def test_qutejavascript_empty_query(self):
        url = QUrl("qute://javascript")

        with pytest.raises(qutescheme.UrlInvalidError):
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
                     "url": QUrl("http://www.x.com/" + str(i)),
                     "title": "Page " + str(i)}
            items.insert(0, entry)

        return items

    @pytest.fixture(autouse=True)
    def fake_history(self, web_history, fake_args, entries):
        """Create fake history."""
        for item in entries:
            web_history.add_url(**item)

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

    def test_exclude(self, web_history, now, config_stub):
        """Make sure the completion.web_history.exclude setting is not used."""
        config_stub.val.completion.web_history.exclude = ['www.x.com']

        url = QUrl("qute://history/data?start_time={}".format(now))
        _mimetype, data = qutescheme.qute_history(url)
        items = json.loads(data)
        assert items

    def test_qute_history_benchmark(self, web_history, benchmark, now):
        r = range(20000)
        entries = {
            'atime': [int(now - t) for t in r],
            'url': ['www.x.com/{}'.format(t) for t in r],
            'title': ['x at {}'.format(t) for t in r],
            'redirect': [False for _ in r],
        }

        web_history.insert_batch(entries)
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


class TestPDFJSHandler:

    """Test the qute://pdfjs endpoint."""

    @pytest.fixture(autouse=True)
    def fake_pdfjs(self, monkeypatch):
        def get_pdfjs_res(path):
            if path == '/existing/file.html':
                return b'foobar'
            raise pdfjs.PDFJSNotFound(path)

        monkeypatch.setattr(pdfjs, 'get_pdfjs_res', get_pdfjs_res)

    @pytest.fixture
    def download_tmpdir(self):
        tdir = downloads.temp_download_manager.get_tmpdir()
        yield py.path.local(tdir.name)  # pylint: disable=no-member
        tdir.cleanup()

    def test_existing_resource(self):
        """Test with a resource that exists."""
        _mimetype, data = qutescheme.data_for_url(
            QUrl('qute://pdfjs/existing/file.html'))
        assert data == b'foobar'

    def test_nonexisting_resource(self, caplog):
        """Test with a resource that does not exist."""
        with caplog.at_level(logging.WARNING, 'misc'):
            with pytest.raises(qutescheme.NotFoundError):
                qutescheme.data_for_url(QUrl('qute://pdfjs/no/file.html'))

        expected = 'pdfjs resource requested but not found: /no/file.html'
        assert caplog.messages == [expected]

    def test_viewer_page(self, data_tmpdir):
        """Load the /web/viewer.html page."""
        filename = 'foobar.pdf'
        path = qutescheme._pdf_path(filename)

        # Make sure that the file exists otherwise the handler will attempt to
        # redirect to source (it's not necessary to make sure that it's valid
        # PDF content)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('<pdf content>')

        _mimetype, data = qutescheme.data_for_url(
            QUrl('qute://pdfjs/web/viewer.html?filename=' + filename))
        assert b'PDF.js' in data

    def test_viewer_no_filename(self):
        with pytest.raises(qutescheme.UrlInvalidError,
                           match='Missing filename'):
            qutescheme.data_for_url(QUrl('qute://pdfjs/web/viewer.html'))

    def test_viewer_inexistent_file(self):
        with pytest.raises(qutescheme.Redirect):
            qutescheme.data_for_url(QUrl('qute://pdfjs/web/viewer.html?'
                                         'filename=foobar&source=example.org'))

    def test_viewer_inexistent_file_no_source(self):
        with pytest.raises(qutescheme.UrlInvalidError,
                           match='Missing source'):
            qutescheme.data_for_url(
                QUrl('qute://pdfjs/web/viewer.html?filename=foobar'))

    def test_file(self, download_tmpdir):
        """Load a file via qute://pdfjs/file."""
        (download_tmpdir / 'testfile').write_binary(b'foo')
        _mimetype, data = qutescheme.data_for_url(
            QUrl('qute://pdfjs/file?filename=testfile'))
        assert data == b'foo'

    def test_file_no_filename(self):
        with pytest.raises(qutescheme.UrlInvalidError):
            qutescheme.data_for_url(QUrl('qute://pdfjs/file'))

    @pytest.mark.parametrize('sep', ['/', os.sep])
    def test_file_pathsep(self, sep):
        url = QUrl('qute://pdfjs/file')
        query = QUrlQuery()
        query.addQueryItem('filename', 'foo{}bar'.format(sep))
        url.setQuery(query)
        with pytest.raises(qutescheme.RequestDeniedError):
            qutescheme.data_for_url(url)
