# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Daniel Schadt
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

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.browser import pdfjs
from qutebrowser.utils import usertypes, utils


@pytest.mark.parametrize('available, snippet', [
    pytest.param(True, '<title>PDF.js viewer</title>',
                 marks=pytest.mark.skipif(not pdfjs.is_available(),
                                          reason='PDF.js unavailable')),
    (False, '<h1>No pdf.js installation found</h1>'),
    ('force', 'fake PDF.js'),
])
def test_generate_pdfjs_page(available, snippet, monkeypatch):
    if available == 'force':
        monkeypatch.setattr(pdfjs, 'is_available', lambda: True)
        monkeypatch.setattr(pdfjs, 'get_pdfjs_res',
                            lambda filename: b'fake PDF.js')
    else:
        monkeypatch.setattr(pdfjs, 'is_available', lambda: available)

    content = pdfjs.generate_pdfjs_page('example.pdf', QUrl())
    print(content)
    assert snippet in content


# Note that we got double protection, once because we use QUrl.FullyEncoded and
# because we use qutebrowser.utils.javascript.string_escape.  Characters
# like " are already replaced by QUrl.
@pytest.mark.parametrize('filename, expected', [
    ('foo.bar', "foo.bar"),
    ('foo"bar', "foo%22bar"),
    ('foo\0bar', 'foo%00bar'),
    ('foobar");alert("attack!");',
     'foobar%22);alert(%22attack!%22);'),
])
def test_generate_pdfjs_script(filename, expected):
    expected_open = 'open("qute://pdfjs/file?filename={}");'.format(expected)
    actual = pdfjs._generate_pdfjs_script(filename)
    assert expected_open in actual
    assert 'PDFView' in actual


@pytest.mark.parametrize('qt, backend, expected', [
    ('new', usertypes.Backend.QtWebEngine, False),
    ('new', usertypes.Backend.QtWebKit, False),
    ('old', usertypes.Backend.QtWebEngine, True),
    ('old', usertypes.Backend.QtWebKit, False),
    ('5.7', usertypes.Backend.QtWebEngine, False),
    ('5.7', usertypes.Backend.QtWebKit, False),
])
def test_generate_pdfjs_script_disable_object_url(monkeypatch,
                                                  qt, backend, expected):
    if qt == 'new':
        monkeypatch.setattr(pdfjs.qtutils, 'version_check',
                            lambda version, exact=False, compiled=True:
                            False if version == '5.7.1' else True)
    elif qt == 'old':
        monkeypatch.setattr(pdfjs.qtutils, 'version_check',
                            lambda version, exact=False, compiled=True: False)
    elif qt == '5.7':
        monkeypatch.setattr(pdfjs.qtutils, 'version_check',
                            lambda version, exact=False, compiled=True:
                            True if version == '5.7.1' else False)
    else:
        raise utils.Unreachable

    monkeypatch.setattr(pdfjs.objects, 'backend', backend)

    script = pdfjs._generate_pdfjs_script('testfile')
    assert ('PDFJS.disableCreateObjectURL' in script) == expected


class TestResources:

    @pytest.fixture
    def read_system_mock(self, mocker):
        return mocker.patch.object(pdfjs, '_read_from_system', autospec=True)

    @pytest.fixture
    def read_file_mock(self, mocker):
        return mocker.patch.object(pdfjs.utils, 'read_file', autospec=True)

    def test_get_pdfjs_res_system(self, read_system_mock):
        read_system_mock.return_value = (b'content', 'path')

        assert pdfjs.get_pdfjs_res_and_path('web/test') == (b'content', 'path')
        assert pdfjs.get_pdfjs_res('web/test') == b'content'

        read_system_mock.assert_called_with('/usr/share/pdf.js/',
                                            ['web/test', 'test'])

    def test_get_pdfjs_res_bundled(self, read_system_mock, read_file_mock):
        read_system_mock.return_value = (None, None)

        read_file_mock.return_value = b'content'

        assert pdfjs.get_pdfjs_res_and_path('web/test') == (b'content', None)
        assert pdfjs.get_pdfjs_res('web/test') == b'content'

        for path in pdfjs.SYSTEM_PDFJS_PATHS:
            read_system_mock.assert_any_call(path, ['web/test', 'test'])

    def test_get_pdfjs_res_not_found(self, read_system_mock, read_file_mock):
        read_system_mock.return_value = (None, None)
        read_file_mock.side_effect = FileNotFoundError

        with pytest.raises(pdfjs.PDFJSNotFound,
                           match="Path 'web/test' not found"):
            pdfjs.get_pdfjs_res_and_path('web/test')


@pytest.mark.parametrize('path, expected', [
    ('web/viewer.js', 'viewer.js'),
    ('build/locale/foo.bar', 'locale/foo.bar'),
    ('viewer.js', 'viewer.js'),
    ('foo/viewer.css', 'foo/viewer.css'),
])
def test_remove_prefix(path, expected):
    assert pdfjs._remove_prefix(path) == expected


@pytest.mark.parametrize('names, expected_name', [
    (['one'], 'one'),
    (['doesnotexist', 'two'], 'two'),
    (['one', 'two'], 'one'),
    (['does', 'not', 'onexist'], None),
])
def test_read_from_system(names, expected_name, tmpdir):
    file1 = tmpdir / 'one'
    file1.write_text('text1', encoding='ascii')
    file2 = tmpdir / 'two'
    file2.write_text('text2', encoding='ascii')

    if expected_name == 'one':
        expected = (b'text1', str(file1))
    elif expected_name == 'two':
        expected = (b'text2', str(file2))
    elif expected_name is None:
        expected = (None, None)

    assert pdfjs._read_from_system(str(tmpdir), names) == expected


@pytest.mark.parametrize('available', [True, False])
def test_is_available(available, mocker):
    mock = mocker.patch.object(pdfjs, 'get_pdfjs_res', autospec=True)
    if available:
        mock.return_value = b'foo'
    else:
        mock.side_effect = pdfjs.PDFJSNotFound('build/pdf.js')

    assert pdfjs.is_available() == available


@pytest.mark.parametrize('mimetype, url, enabled, expected', [
    # PDF files
    ('application/pdf', 'http://www.example.com', True, True),
    ('application/x-pdf', 'http://www.example.com', True, True),
    # Not a PDF
    ('application/octet-stream', 'http://www.example.com', True, False),
    # PDF.js disabled
    ('application/pdf', 'http://www.example.com', False, False),
    # Download button in PDF.js
    ('application/pdf', 'blob:qute%3A///b45250b3', True, False),
])
def test_should_use_pdfjs(mimetype, url, enabled, expected, config_stub):
    config_stub.val.content.pdfjs = enabled
    assert pdfjs.should_use_pdfjs(mimetype, QUrl(url)) == expected


def test_get_main_url():
    expected = ('qute://pdfjs/web/viewer.html?filename='
                'hello?world.pdf&file=')
    assert pdfjs.get_main_url('hello?world.pdf') == QUrl(expected)
