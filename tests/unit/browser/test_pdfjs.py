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
from qutebrowser.utils import usertypes


@pytest.mark.parametrize('available, snippet', [
    (True, '<title>PDF.js viewer</title>'),
    (False, '<h1>No pdf.js installation found</h1>'),
])
def test_generate_pdfjs_page(available, snippet, monkeypatch):
    monkeypatch.setattr(pdfjs, 'is_available', lambda: available)
    content = pdfjs.generate_pdfjs_page(QUrl('https://example.com/'))
    print(content)
    assert snippet in content


# Note that we got double protection, once because we use QUrl.FullyEncoded and
# because we use qutebrowser.utils.javascript.string_escape.  Characters
# like " are already replaced by QUrl.
@pytest.mark.parametrize('url, expected', [
    ('http://foo.bar', "http://foo.bar"),
    ('http://"', ''),
    ('\0', '%00'),
    ('http://foobar/");alert("attack!");',
     'http://foobar/%22);alert(%22attack!%22);'),
])
def test_generate_pdfjs_script(url, expected):
    expected_open = 'open("{}");'.format(expected)
    url = QUrl(url)
    actual = pdfjs._generate_pdfjs_script(url)
    assert expected_open in actual
    assert 'PDFView' in actual


@pytest.mark.parametrize('new_qt, backend, expected', [
    (True, usertypes.Backend.QtWebEngine, False),
    (True, usertypes.Backend.QtWebKit, False),
    (False, usertypes.Backend.QtWebEngine, True),
    (False, usertypes.Backend.QtWebKit, False),
])
def test_generate_pdfjs_script_disable_object_url(monkeypatch,
                                                  new_qt, backend, expected):
    monkeypatch.setattr(pdfjs.qtutils, 'version_check', lambda _v: new_qt)
    monkeypatch.setattr(pdfjs.objects, 'backend', backend)

    script = pdfjs._generate_pdfjs_script(QUrl('https://example.com/'))
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


@pytest.mark.parametrize('mimetype, enabled, expected', [
    ('application/pdf', True, True),
    ('application/x-pdf', True, True),
    ('application/octet-stream', True, False),
    ('application/pdf', False, False),
])
def test_should_use_pdfjs(mimetype, enabled, expected, config_stub):
    config_stub.val.content.pdfjs = enabled
    assert pdfjs.should_use_pdfjs(mimetype) == expected


def test_get_main_url():
    expected = ('qute://pdfjs/web/viewer.html?file='
                'qute://pdfjs/file?filename%3Dhello?world.pdf')
    assert pdfjs.get_main_url('hello?world.pdf') == QUrl(expected)
