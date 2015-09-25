# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
import io
import textwrap
import re

import pytest

from qutebrowser.browser import mhtml

@pytest.fixture(autouse=True)
def patch_uuid(monkeypatch):
    monkeypatch.setattr("uuid.uuid4", lambda: "UUID")


class Checker:

    """A helper to check mhtml output.

    Attrs:
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

        Die=20s=FC=DFe=20H=FCndin=20l=E4uft=20in=20die=20H=F6hle=20des=20B=E4ren
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
    with pytest.raises(UnicodeEncodeError) as excinfo:
        writer.write_to(checker.fp)
    assert "'ascii' codec can't encode" in str(excinfo.value)


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

        Image=20file=20attached
        -----=_qute-UUID
        Content-Location: http://a.example.com/image.png
        MIME-Version: 1.0
        Content-Type: image/png
        Content-Transfer-Encoding: base64

        8J+YgSBpbWFnZSBkYXRh

        -----=_qute-UUID--
        """)


@pytest.mark.parametrize('transfer_encoding', [mhtml.E_BASE64, mhtml.E_QUOPRI],
                         ids=['base64', 'quoted-printable'])
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

        root=20file
        -----=_qute-UUID
        Content-Location: http://a.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file=20a
        -----=_qute-UUID
        Content-Location: http://b.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file=20b
        -----=_qute-UUID
        Content-Location: http://g.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file=20g
        -----=_qute-UUID
        Content-Location: http://h.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file=20h
        -----=_qute-UUID
        Content-Location: http://i.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file=20i
        -----=_qute-UUID
        Content-Location: http://t.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file=20t
        -----=_qute-UUID
        Content-Location: http://z.example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        file=20z
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

        file=20content
        -----=_qute-UUID--
        """)


def test_removing_file_from_mhtml(checker):
    writer = mhtml.MHTMLWriter(root_content=b'root',
                               content_location='http://example.com/',
                               content_type='text/plain')
    writer.add_file('http://evil.com/', b'file content')
    writer.remove_file('http://evil.com/')
    writer.write_to(checker.fp)
    checker.expect("""
        Content-Type: multipart/related; boundary="---=_qute-UUID"
        MIME-Version: 1.0

        -----=_qute-UUID
        Content-Location: http://example.com/
        MIME-Version: 1.0
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable

        root
        -----=_qute-UUID--
        """)


@pytest.mark.parametrize('has_cssutils', [True, False])
@pytest.mark.parametrize('inline, style, expected_urls', [
    (False, "@import 'default.css'", ['default.css']),
    (False, '@import "default.css"', ['default.css']),
    (False, "@import \t 'tabbed.css'", ['tabbed.css']),
    (False, "@import url('default.css')", ['default.css']),
    (False, """body {
    background: url("/bg-img.png")
    }""", ['/bg-img.png']),
    (True, 'background: url(folder/file.png) no-repeat', ['folder/file.png']),
    (True, 'content: url()', []),
])
def test_css_url_scanner(monkeypatch, has_cssutils, inline, style,
                         expected_urls):
    if has_cssutils:
        assert mhtml.cssutils is not None
    else:
        monkeypatch.setattr('qutebrowser.browser.mhtml.cssutils', None)
    expected_urls.sort()
    urls = mhtml._get_css_imports(style, inline=inline)
    urls.sort()
    assert urls == expected_urls


class TestNoCloseBytesIO:
    # WORKAROUND for https://bitbucket.org/logilab/pylint/issues/540/
    # pylint: disable=no-member

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
        with pytest.raises(ValueError) as excinfo:
            fp.getvalue()
        assert str(excinfo.value) == 'I/O operation on closed file.'
        with pytest.raises(ValueError) as excinfo:
            fp.write(b'Closed')
        assert str(excinfo.value) == 'I/O operation on closed file.'
