# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os.path
import base64

import pytest
pytest.importorskip('PyQt5.QtWebEngineWidgets')
from PyQt5.QtWebEngineWidgets import QWebEngineProfile

from qutebrowser.utils import urlutils
from qutebrowser.browser.webengine import webenginedownloads


@pytest.mark.parametrize('path, expected', [
    (os.path.join('subfolder', 'foo'), 'foo'),
    ('foo(1)', 'foo'),
    ('foo (1)', 'foo'),
    ('foo - 1970-01-01T00:00:00.000Z', 'foo'),
    ('foo(a)', 'foo(a)'),
    ('foo1', 'foo1'),
    ('foo%20bar', 'foo%20bar'),
    ('foo%2Fbar', 'foo%2Fbar'),
])
def test_get_suggested_filename(path, expected):
    assert webenginedownloads._get_suggested_filename(path) == expected


@pytest.mark.parametrize('with_slash', [True, False])
def test_data_url_workaround_needed(qapp, qtbot, webengineview, with_slash):
    """With data URLs, we get rather weird base64 filenames back from QtWebEngine.

    This test verifies that our workaround for this is still needed, i.e. if we get
    those base64-filenames rather than a "download.pdf" like with Chromium.
    """
    # https://stackoverflow.com/a/17280876/2085149
    pdf_source = [
        '%PDF-1.0',
        '1 0 obj<</Pages 2 0 R>>endobj',
        '2 0 obj<</Kids[3 0 R]/Count 1>>endobj',
        '3 0 obj<</MediaBox[0 0 3 3]>>endobj',
        'trailer<</Root 1 0 R>>',
    ]

    if with_slash:
        pdf_source.insert(1, '% ?')  # this results in a slash in base64

    pdf_data = '\n'.join(pdf_source).encode('ascii')
    base64_data = base64.b64encode(pdf_data).decode('ascii')

    if with_slash:
        assert '/' in base64_data
        expected = base64_data.split('/')[1]
    else:
        assert '/' not in base64_data
        expected = 'pdf'  # from the mimetype

    def check_item(item):
        assert item.mimeType() == 'application/pdf'
        assert item.url().scheme() == 'data'
        assert os.path.basename(item.path()) == expected
        return True

    profile = QWebEngineProfile.defaultProfile()
    profile.setParent(qapp)

    url = urlutils.data_url('application/pdf', pdf_data)

    with qtbot.waitSignal(profile.downloadRequested, check_params_cb=check_item):
        webengineview.load(url)
