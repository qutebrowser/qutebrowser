# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015-2018 Daniel Schadt
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

import io
import textwrap
import re

import pytest

mhtml = pytest.importorskip('qutebrowser.browser.webkit.mhtml')


try:
    import cssutils
except (ImportError, re.error):
    # Catching re.error because cssutils in earlier releases (<= 1.0) is
    # broken on Python 3.5
    # See https://bitbucket.org/cthedot/cssutils/issues/52
    cssutils = None


@pytest.fixture(autouse=True)
def patch_uuid(monkeypatch):
    monkeypatch.setattr("uuid.uuid4", lambda: "UUID")


class Checker:

    """A helper to check mhtml output.

    Attributes:
        fp: A BytesIO object for passing to MHTMLWriter.write_to.
    """

    def __init__(self):
        self.fp = io.BytesIO()

    @property
    def value(self):
        return self.fp.getvalue()

    def expect(self, expected):
        actual = self.value.decode('ascii')
        # Make sure there are no stray \r or \n
        assert re.search(r'\r[^\n]', actual) is None
        assert re.search(r'[^\r]\n', actual) is None
        actual = actual.replace('\r\n', '\n')
        expected = textwrap.dedent(expected).lstrip('\n')
        assert expected == actual


@pytest.fixture
def checker():
    return Checker()


def test_quoted_printable_umlauts(checker):
    content = 'Die süße Hündin läuft in die Höhle des Bären'
    content = content.encode('iso-8859-1')
    writer = mhtml.MHTMLWriter(root_content=content,
                               content_location='localhost',
                               content_type='text/plain')
    writer.write_to(checker.fp)
    checker.expect("""
        Content-Type: multipart/related; boundary="---=_qute-UUID"
        MIME-Version: 1.0

        -----=_qute-UUID
        Content-Location: localhost
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        Die s=FC=DFe H=FCndin l=E4uft in die H=F6hle des B=E4ren
        -----=_qute-UUID--
        """)


@pytest.mark.parametrize('header, value', [
    ('content_location', 'http://brötli.com'),
    ('content_type', 'text/pläin'),
])
def test_refuses_non_ascii_header_value(checker, header, value):
    defaults = {
        'root_content': b'',
        'content_location': 'http://example.com',
        'content_type': 'text/plain',
    }
    defaults[header] = value
    writer = mhtml.MHTMLWriter(**defaults)
    with pytest.raises(UnicodeEncodeError, match="'ascii' codec can't encode"):
        writer.write_to(checker.fp)


def test_file_encoded_as_base64(checker):
    content = b'Image file attached'
    writer = mhtml.MHTMLWriter(root_content=content, content_type='text/plain',
                               content_location='http://example.com')
    writer.add_file(location='http://a.example.com/image.png',
                    content='\U0001F601 image data'.encode('utf-8'),
                    content_type='image/png',
                    transfer_encoding=mhtml.E_BASE64)
    writer.write_to(checker.fp)
    checker.expect("""
        Content-Type: multipart/related; boundary="---=_qute-UUID"
        MIME-Version: 1.0

        -----=_qute-UUID
        Content-Location: http://example.com
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        Image file attached
        -----=_qute-UUID
        Content-Location: http://a.example.com/image.png
        MIME-Version: 1.0
        Content-Type: image/png
        Content-Transfer-Encoding: base64

        8J+YgSBpbWFnZSBkYXRh

        -----=_qute-UUID--
        """)


@pytest.mark.parametrize('transfer_encoding', [
    pytest.param(mhtml.E_BASE64, id='base64'),
    pytest.param(mhtml.E_QUOPRI, id='quoted-printable')])
def test_payload_lines_wrap(checker, transfer_encoding):
    payload = b'1234567890' * 10
    writer = mhtml.MHTMLWriter(root_content=b'', content_type='text/plain',
                               content_location='http://example.com')
    writer.add_file(location='http://example.com/payload', content=payload,
                    content_type='text/plain',
                    transfer_encoding=transfer_encoding)
    writer.write_to(checker.fp)
    for line in checker.value.split(b'\r\n'):
        assert len(line) < 77


def test_files_appear_sorted(checker):
    writer = mhtml.MHTMLWriter(root_content=b'root file',
                               content_type='text/plain',
                               content_location='http://www.example.com/')
    for subdomain in 'ahgbizt':
        writer.add_file(location='http://{}.example.com/'.format(subdomain),
                        content='file {}'.format(subdomain).encode('utf-8'),
                        content_type='text/plain',
                        transfer_encoding=mhtml.E_QUOPRI)
    writer.write_to(checker.fp)
    checker.expect("""
        Content-Type: multipart/related; boundary="---=_qute-UUID"
        MIME-Version: 1.0

        -----=_qute-UUID
        Content-Location: http://www.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        root file
        -----=_qute-UUID
        Content-Location: http://a.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file a
        -----=_qute-UUID
        Content-Location: http://b.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file b
        -----=_qute-UUID
        Content-Location: http://g.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file g
        -----=_qute-UUID
        Content-Location: http://h.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file h
        -----=_qute-UUID
        Content-Location: http://i.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file i
        -----=_qute-UUID
        Content-Location: http://t.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file t
        -----=_qute-UUID
        Content-Location: http://z.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file z
        -----=_qute-UUID--
        """)


def test_empty_content_type(checker):
    writer = mhtml.MHTMLWriter(root_content=b'',
                               content_location='http://example.com/',
                               content_type='text/plain')
    writer.add_file('http://example.com/file', b'file content')
    writer.write_to(checker.fp)
    checker.expect("""
        Content-Type: multipart/related; boundary="---=_qute-UUID"
        MIME-Version: 1.0

        -----=_qute-UUID
        Content-Location: http://example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable


        -----=_qute-UUID
        MIME-Version: 1.0
        Content-Location: http://example.com/file
        Content-Transfer-Encoding: quoted-printable

        file content
        -----=_qute-UUID--
        """)


@pytest.mark.parametrize('has_cssutils', [
    pytest.param(True, marks=pytest.mark.skipif(
        cssutils is None, reason="requires cssutils"), id='with_cssutils'),
    pytest.param(False, id='no_cssutils'),
])
@pytest.mark.parametrize('inline, style, expected_urls', [
    pytest.param(False, "@import 'default.css'", ['default.css'],
                 id='import with apostrophe'),
    pytest.param(False, '@import "default.css"', ['default.css'],
                 id='import with quote'),
    pytest.param(False, "@import \t 'tabbed.css'", ['tabbed.css'],
                 id='import with tab'),
    pytest.param(False, "@import url('default.css')", ['default.css'],
                 id='import with url()'),
    pytest.param(False, """body {
    background: url("/bg-img.png")
    }""", ['/bg-img.png'], id='background with body'),
    pytest.param(True, 'background: url(folder/file.png) no-repeat',
                 ['folder/file.png'], id='background'),
    pytest.param(True, 'content: url()', [], id='content'),
])
def test_css_url_scanner(monkeypatch, has_cssutils, inline, style,
                         expected_urls):
    if not has_cssutils:
        monkeypatch.setattr(mhtml, '_get_css_imports_cssutils',
                            lambda data, inline=False: None)
    expected_urls.sort()
    urls = mhtml._get_css_imports(style, inline=inline)
    urls.sort()
    assert urls == expected_urls


def test_quoted_printable_spaces(checker):
    content = b' ' * 100
    writer = mhtml.MHTMLWriter(root_content=content,
                               content_location='localhost',
                               content_type='text/plain')
    writer.write_to(checker.fp)
    checker.expect("""
        Content-Type: multipart/related; boundary="---=_qute-UUID"
        MIME-Version: 1.0

        -----=_qute-UUID
        Content-Location: localhost
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        {}=
        {}=20
        -----=_qute-UUID--
        """.format(' ' * 75, ' ' * 24))


class TestNoCloseBytesIO:

    def test_fake_close(self):
        fp = mhtml._NoCloseBytesIO()
        fp.write(b'Value')
        fp.close()
        assert fp.getvalue() == b'Value'
        fp.write(b'Eulav')
        assert fp.getvalue() == b'ValueEulav'

    def test_actual_close(self):
        fp = mhtml._NoCloseBytesIO()
        fp.write(b'Value')
        fp.actual_close()
        with pytest.raises(ValueError, match="I/O operation on closed file."):
            fp.getvalue()
        with pytest.raises(ValueError, match="I/O operation on closed file."):
            fp.getvalue()
            fp.write(b'Closed')
