# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import logging

import pytest

from qutebrowser.browser.webkit import http


DEFAULT_NAME = 'qutebrowser-download'


class HeaderChecker:

    """Helper class with some convenience methods to check filenames.

    Attributes:
        caplog: fixture from pytest-capturelog
        stubs: fixture that provides testing stubs
    """

    def __init__(self, caplog, stubs):
        self.caplog = caplog
        self.stubs = stubs

    def check_filename(self, header, filename, expected_inline=False):
        """Check if the passed header has the given filename."""
        reply = self.stubs.FakeNetworkReply(
            headers={'Content-Disposition': header})
        cd_inline, cd_filename = http.parse_content_disposition(reply)
        assert cd_filename is not None
        assert cd_filename == filename
        assert cd_inline == expected_inline

    def check_ignored(self, header):
        """Check if the passed header is ignored."""
        reply = self.stubs.FakeNetworkReply(
            headers={'Content-Disposition': header})
        with self.caplog.at_level(logging.ERROR, 'rfc6266'):
            # with self.assertLogs(log.rfc6266, logging.ERROR):
            cd_inline, cd_filename = http.parse_content_disposition(reply)
        assert cd_filename == DEFAULT_NAME
        assert cd_inline

    def check_unnamed(self, header):
        """Check if the passed header results in an unnamed attachment."""
        reply = self.stubs.FakeNetworkReply(
            headers={'Content-Disposition': header})
        cd_inline, cd_filename = http.parse_content_disposition(reply)
        assert cd_filename == DEFAULT_NAME
        assert not cd_inline


@pytest.fixture
def header_checker(caplog, stubs):
    """Fixture that provides a HeaderChecker class for tests"""
    return HeaderChecker(caplog, stubs)


def test_att_double_space(header_checker):
    """'attachment' with double space in the filename."""
    header_checker.check_filename('attachment; filename="foo  bar.html"',
                                  'foo bar.html')


def test_iso2231_langtag(header_checker):
    """'attachment', specifying a filename of foo-ä.html with language tag.

    Using RFC2231/5987 encoded ISO-8859-1.
    UA should offer to download the resource as "foo-ä.html".
    """
    header_checker.check_filename(
        "attachment; filename*=iso-8859-1'de'foo-%E4.html",
        'foo-ä.html')


def test_iso2231_iso8859_invalid_chars(header_checker):
    """'attachment', specifying a filename with invalid ISO-8859-1 chars."""
    header_checker.check_ignored(
        "attachment; filename*=iso-8859-1''foo-%80.html")


# All following test cases are based on http://greenbytes.de/tech/tc2231/


class TestInline:

    """Various tests relating to the "inline" disposition type.

    See Section 4.2 of RFC 6266.
    """

    def test_inlonly(self, header_checker):
        """'inline' only

        This should be equivalent to not including the header at all.
        """
        header_checker.check_ignored('inline')

    def test_inlonlyquoted(self, header_checker):
        """'inline' only, using double quotes

        This is invalid syntax, thus the header should be ignored.
        """
        header_checker.check_ignored('"inline"')

    def test_inlwithasciifilename(self, header_checker):
        """'inline', specifying a filename of foo.html

        Some UAs use this filename in a subsequent "save" operation.
        """
        header_checker.check_filename('inline; filename="foo.html"',
                                      'foo.html', expected_inline=True)

    def test_inlwithfnattach(self, header_checker):
        """'inline', specifying a filename of "Not an attachment!".

        This checks for proper parsing for disposition types.
        """
        header_checker.check_filename('inline; filename="Not an attachment!"',
                                      "Not an attachment!",
                                      expected_inline=True)

    def test_inlwithasciifilenamepdf(self, header_checker):
        """'inline', specifying a filename of foo.pdf.

        Some UAs use this filename in a subsequent "save" operation. This
        variation of the test checks whether whatever handles PDF display
        receives the filename information, and acts upon it (this was tested
        with the latest Acrobat Reader plugin, or, in the case of Chrome, using
        the built-in PDF handler).
        """
        header_checker.check_filename('inline; filename="foo.pdf"', "foo.pdf",
                                      expected_inline=True)


class TestAttachment:

    """Various tests relating to the "attachment" disposition type.

    See Section 4.2 of RFC 6266.
    """

    def test_attonly(self, stubs):
        """'attachment' only.

        UA should offer to download the resource.
        """
        reply = stubs.FakeNetworkReply(
            headers={'Content-Disposition': 'attachment'})
        cd_inline, cd_filename = http.parse_content_disposition(reply)
        assert not cd_inline
        assert cd_filename == DEFAULT_NAME

    def test_attonlyquoted(self, header_checker):
        """'attachment' only, using double quotes

        This is invalid syntax, thus the header should be ignored.
        """
        header_checker.check_ignored('"attachment"')

    # we can't test attonly403 here.

    def test_attonlyucase(self, header_checker):
        """'ATTACHMENT' only

        UA should offer to download the resource.
        """
        header_checker.check_unnamed('ATTACHMENT')

    def test_attwithasciifilename(self, header_checker):
        """'attachment', specifying a filename of foo.html

        UA should offer to download the resource as "foo.html".
        """
        header_checker.check_filename('attachment; filename="foo.html"',
                                      'foo.html')

    def test_attwithasciifilename25(self, header_checker):
        """'attachment', with a 25 character filename."""
        header_checker.check_filename(
            'attachment; filename="0000000000111111111122222"',
            '0000000000111111111122222')

    def test_attwithasciifilename35(self, header_checker):
        """'attachment', with a 35 character filename."""
        header_checker.check_filename(
            'attachment; filename="00000000001111111111222222222233333"',
            '00000000001111111111222222222233333')

    def test_attwithasciifnescapedchar(self, header_checker):
        r"""'attachment', specifying a filename of f\oo.html.

        (the first 'o' being escaped)
        UA should offer to download the resource as "foo.html".
        """
        header_checker.check_filename(r'attachment; filename="f\oo.html"',
                                      'foo.html')

    def test_attwithasciifnescapedquote(self, header_checker):
        r"""'attachment', specifying a filename of \"quoting\" tested.html

        (using double quotes around "quoting" to test... quoting)

        UA should offer to download the resource as something like '"quoting"
        tested.html' (stripping the quotes may be ok for security reasons, but
        getting confused by them is not).
        """
        header = r'attachment; filename="\"quoting\" tested.html"'
        header_checker.check_filename(header, '"quoting" tested.html')

    def test_attwithquotedsemicolon(self, header_checker):
        """'attachment', specifying a filename of Here's a semicolon;.html.

        This checks for proper parsing for parameters.
        """
        header_checker.check_filename(
            'attachment; filename="Here\'s a semicolon;.html"',
            "Here's a semicolon;.html")

    def test_attwithfilenameandextparam(self, header_checker):
        """'attachment', specifying a filename of foo.html.

        And an extension parameter "foo" which should be ignored (see Section
        4.4 of RFC 6266.).

        UA should offer to download the resource as "foo.html".
        """
        header_checker.check_filename(
            'attachment; foo="bar"; filename="foo.html"',
            'foo.html')

    def test_attwithfilenameandextparamescaped(self, header_checker):
        """'attachment', specifying a filename of foo.html.

        And an extension parameter "foo" which should be ignored (see Section
        4.4 of RFC 6266.). In comparison to attwithfilenameandextparam, the
        extension parameter actually uses backslash-escapes. This tests whether
        the UA properly skips the parameter.

        UA should offer to download the resource as "foo.html".
        """
        header_checker.check_filename(
            r'attachment; foo="\"\\";filename="foo.html"', 'foo.html')

    def test_attwithasciifilenameucase(self, header_checker):
        """'attachment', specifying a filename of foo.html

        UA should offer to download the resource as "foo.html".
        """
        header_checker.check_filename(r'attachment; FILENAME="foo.html"',
                                      'foo.html')

    def test_attwithasciifilenamenq(self, header_checker):
        """'attachment', specifying a filename of foo.html.

        (using a token instead of a quoted-string).

        Note that was invalid according to Section 19.5.1 of RFC 2616.
        """
        header_checker.check_filename('attachment; filename=foo.html',
                                      'foo.html')

    def test_attwithtokfncommanq(self, header_checker):
        """'attachment', specifying a filename of foo,bar.html.

        (using a comma despite using token syntax).
        """
        header_checker.check_ignored('attachment; filename=foo,bar.html')

    @pytest.mark.xfail(reason='With relaxed=True we accept that')
    def test_attwithasciifilenamenqs(self, header_checker):
        """'attachment', specifying a filename of foo.html.

        (using a token instead of a quoted-string, and adding a trailing
        semicolon).

        The trailing semicolon makes the header field value syntactically
        incorrect, as no other parameter follows. Thus the header field should
        be ignored.
        """
        header_checker.check_ignored('attachment; filename=foo.html ;')

    def test_attemptyparam(self, header_checker):
        """'attachment', specifying a filename of foo.

        (but including an empty parameter).

        The empty parameter makes the header field value syntactically
        incorrect, as no other parameter follows. Thus the header field should
        be ignored.
        """
        header_checker.check_ignored('attachment; ;filename=foo')

    def test_attwithasciifilenamenqws(self, header_checker):
        """'attachment', specifying a filename of foo bar.html.

        (without using quoting).

        This is invalid. "token" does not allow whitespace.
        """
        header_checker.check_ignored('attachment; filename=foo bar.html')

    def test_attwithfntokensq(self, header_checker):
        """'attachment', specifying a filename of 'foo.bar'

        (using single quotes).
        """
        header_checker.check_filename("attachment; filename='foo.bar'",
                                      "'foo.bar'")

    def test_attwithisofnplain(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        (using plain ISO-8859-1)

        UA should offer to download the resource as "foo-ä.html".
        """
        header_checker.check_filename('attachment; filename="foo-ä.html"',
                                      'foo-ä.html')

    def test_attwithutf8fnplain(self, header_checker):
        """'attachment', specifying a filename of foo-Ã¤.html.

        (which happens to be foo-ä.html using UTF-8 encoding).

        UA should offer to download the resource as "foo-Ã¤.html". Displaying
        "foo-ä.html" instead indicates that the UA tried to be smart by
        detecting something that happens to look like UTF-8.
        """
        header_checker.check_filename('attachment; filename="foo-Ã¤.html"',
                                      'foo-Ã¤.html')

    def test_attwithfnrawpctenca(self, header_checker):
        """'attachment', specifying a filename of foo-%41.html

        UA should offer to download the resource as "foo-%41.html". Displaying
        "foo-A.html" instead would indicate that the UA has attempted to
        percent-decode the parameter.
        """
        header_checker.check_filename('attachment; filename="foo-%41.html"',
                                      'foo-%41.html')

    def test_attwithfnusingpct(self, header_checker):
        """'attachment', specifying a filename of 50%.html

        UA should offer to download the resource as "50%.html". This tests how
        UAs that fails at attwithfnrawpctenca handle "%" characters that do not
        start a "% hexdig hexdig" sequence.
        """
        header_checker.check_filename('attachment; filename="50%.html"',
                                      '50%.html')

    def test_attwithfnrawpctencaq(self, header_checker):
        """'attachment', specifying a filename of foo-%41.html.

        Using an escape character (this tests whether adding an escape
        character inside a %xx sequence can be used to disable the
        non-conformant %xx-unescaping).

        UA should offer to download the resource as "foo-%41.html".
        """
        header_checker.check_filename(r'attachment; filename="foo-%\41.html"',
                                      'foo-%41.html')

    def test_attwithnamepct(self, header_checker):
        """'attachment', specifying a name parameter of foo-%41.html.

        (This test was added to observe the behavior of the (unspecified)
        treatment of "name" as synonym for "filename"; see Ned Freed's
        summary[1] where this comes from in MIME messages)

        Should be treated as extension parameter, therefore almost any behavior
        is acceptable.

        [1] http://www.imc.org/ietf-smtp/mail-archive/msg05023.html
        """
        header_checker.check_unnamed('attachment; name="foo-%41.html"')

    def test_attwithfilenamepctandiso(self, header_checker):
        """'attachment', specifying a filename parameter of ä-%41.html.

        (this test was added to observe the behavior when non-ASCII characters
        and percent-hexdig sequences are combined)
        """
        header_checker.check_filename('attachment; filename="ä-%41.html"',
                                      'ä-%41.html')

    def test_attwithfnrawpctenclong(self, header_checker):
        """'attachment', specifying a filename of foo-%c3%a4-%e2%82%ac.html.

        (using raw percent encoded UTF-8 to represent foo-ä-€.html)

        UA should offer to download the resource as
        "foo-%c3%a4-%e2%82%ac.html". Displaying "foo-ä-€.html" instead would
        indicate that the UA has attempted to percent-decode the parameter
        (using UTF-8). Displaying something else would indicate that the UA
        tried to percent-decode, but used a different encoding.
        """
        header_checker.check_filename(
            'attachment; filename="foo-%c3%a4-%e2%82%ac.html"',
            'foo-%c3%a4-%e2%82%ac.html')

    def test_attwithasciifilenamews1(self, header_checker):
        """'attachment', specifying a filename of foo.html.

        (With one blank space before the equals character).

        UA should offer to download the resource as "foo.html".
        """
        header_checker.check_filename('attachment; filename ="foo.html"',
                                      'foo.html')

    def test_attwith2filenames(self, header_checker):
        """'attachment', specifying two filename parameters.

        This is invalid syntax.
        """
        header_checker.check_ignored(
            'attachment; filename="foo.html"; filename="bar.html"')

    def test_attfnbrokentoken(self, header_checker):
        """'attachment', specifying a filename of foo[1](2).html.

        Missing the quotes. Also, "[", "]", "(" and ")" are not allowed in the
        HTTP token production.

        This is invalid according to Section 19.5.1 of RFC 2616 and RFC 6266,
        so UAs should ignore it.
        """
        header_checker.check_ignored('attachment; filename=foo[1](2).html')

    def test_attfnbrokentokeniso(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Missing the quotes.

        This is invalid, as the umlaut is not a valid token character, so UAs
        should ignore it.
        """
        header_checker.check_ignored('attachment; filename=foo-ä.html')

    def test_attfnbrokentokenutf(self, header_checker):
        """'attachment', specifying a filename of foo-Ã¤.html.

        (which happens to be foo-ä.html using UTF-8 encoding) but missing the
        quotes.

        This is invalid, as the umlaut is not a valid token character, so UAs
        should ignore it.
        """
        header_checker.check_ignored('attachment; filename=foo-Ã¤.html')

    def test_attmissingdisposition(self, header_checker):
        """Disposition type missing, filename specified.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('filename=foo.html')

    def test_attmissingdisposition2(self, header_checker):
        """Disposition type missing, filename specified after extension.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('x=y; filename=foo.html')

    def test_attmissingdisposition3(self, header_checker):
        """Disposition type missing, filename "qux".

        Can it be more broken? (Probably)
        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('"foo; filename=bar;baz"; filename=qux')

    def test_attmissingdisposition4(self, header_checker):
        """Disposition type missing.

        Two filenames specified separated by a comma (this is syntactically
        equivalent to have two instances of the header with one filename
        parameter each).

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('filename=foo.html, filename=bar.html')

    def test_emptydisposition(self, header_checker):
        """Disposition type missing (but delimiter present).

        Filename specified.
        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('; filename=foo.html')

    def test_doublecolon(self, header_checker):
        """Header field value starts with a colon.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored(': inline; attachment; filename=foo.html')

    def test_attandinline(self, header_checker):
        """Both disposition types specified.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('inline; attachment; filename=foo.html')

    def test_attandinline2(self, header_checker):
        """Both disposition types specified.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('attachment; inline; filename=foo.html')

    def test_attbrokenquotedfn(self, header_checker):
        """'attachment', specifying a filename parameter that is broken.

        (quoted-string followed by more characters). This is invalid syntax.
        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('attachment; filename="foo.html".txt')

    def test_attbrokenquotedfn2(self, header_checker):
        """'attachment', specifying a filename parameter that is broken.

        (missing ending double quote). This is invalid syntax.
        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('attachment; filename="bar')

    def test_attbrokenquotedfn3(self, header_checker):
        """'attachment', specifying a filename parameter that is broken.

        (disallowed characters in token syntax). This is invalid syntax.
        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('attachment; filename=foo"bar;baz"qux')

    def test_attmultinstances(self, header_checker):
        """'attachment', two comma-separated instances of the header field.

        As Content-Disposition doesn't use a list-style syntax, this is invalid
        syntax and, according to RFC 2616, Section 4.2, roughly equivalent to
        having two separate header field instances.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored(
            'attachment; filename=foo.html, attachment; filename=bar.html')

    def test_attmissingdelim(self, header_checker):
        """Uses two parameters, but the mandatory delimiter ";" is missing.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('attachment; foo=foo filename=bar')

    def test_attmissingdelim2(self, header_checker):
        """Uses two parameters, but the mandatory delimiter ";" is missing.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('attachment; filename=bar foo=foo')

    def test_attmissingdelim3(self, header_checker):
        """';' missing between disposition type and filename parameter.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('attachment filename=bar')

    def test_attreversed(self, header_checker):
        """filename parameter and disposition type reversed.

        This is invalid, so UAs should ignore it.
        """
        header_checker.check_ignored('filename=foo.html; attachment')

    def test_attconfusedparam(self, header_checker):
        """'attachment', specifying an "xfilename" parameter.

        Should be treated as unnamed attachment.
        """
        header_checker.check_unnamed('attachment; xfilename=foo.html')

    def test_attabspath(self, header_checker):
        """'attachment', specifying an absolute filename in the fs root.

        Either ignore the filename altogether, or discard the path information.
        """
        header_checker.check_filename('attachment; filename="/foo.html"',
                                      'foo.html')

    @pytest.mark.posix
    def test_attabspathwin_unix(self, header_checker):
        """'attachment', specifying an absolute filename in the fs root.

        Either ignore the filename altogether, or discard the path information.

        Note that test results under Operating Systems other than Windows vary
        (see
        http://lists.w3.org/Archives/Public/ietf-http-wg/2011JanMar/0112.html);
        apparently some UAs consider the backslash a legitimate filename
        character.
        """
        header_checker.check_filename(r'attachment; filename="\\foo.html"',
                                      r'\foo.html')

    @pytest.mark.windows
    def test_attabspathwin_win(self, header_checker):
        """'attachment', specifying an absolute filename in the fs root.

        Either ignore the filename altogether, or discard the path information.

        Note that test results under Operating Systems other than Windows vary
        (see
        http://lists.w3.org/Archives/Public/ietf-http-wg/2011JanMar/0112.html);
        apparently some UAs consider the backslash a legitimate filename
        character.
        """
        header_checker.check_filename(r'attachment; filename="\\foo.html"',
                                      'foo.html')


# Note we do not check the "Additional parameters" section.


class TestDispositionTypeExtension:

    """Tests checking behavior for disposition type extensions.

    They should be treated as "attachment", see Section 4.2 of RFC 6266.
    """

    def test_dispext(self, header_checker):
        """'foobar' only

        This should be equivalent to using "attachment".
        """
        header_checker.check_unnamed('foobar')

    def test_dispextbadfn(self, header_checker):
        """'attachment', with no filename parameter"""
        header_checker.check_unnamed(
            'attachment; example="filename=example.txt"')


class TestCharacterSet:

    """Various tests using the parameter value encoding defined in RFC 5987."""

    def test_attwithisofn2231iso(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Using RFC2231/5987 encoded ISO-8859-1.
        UA should offer to download the resource as "foo-ä.html".
        """
        header_checker.check_filename(
            "attachment; filename*=iso-8859-1''foo-%E4.html",
            'foo-ä.html')

    def test_attwithfn2231utf8(self, header_checker):
        """'attachment', specifying a filename of foo-ä-€.html.

        Using RFC2231/5987 encoded UTF-8.
        UA should offer to download the resource as "foo-ä-€.html".
        """
        header_checker.check_filename(
            "attachment; filename*=UTF-8''foo-%c3%a4-%e2%82%ac.html",
            'foo-ä-€.html')

    def test_attwithfn2231noc(self, header_checker):
        """Behavior is undefined in RFC 2231.

        The charset part is missing, although UTF-8 was used.
        """
        header_checker.check_ignored(
            "attachment; filename*=''foo-%c3%a4-%e2%82%ac.html")

    def test_attwithfn2231utf8comp(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Using RFC2231 encoded UTF-8, but choosing the decomposed form
        (lowercase a plus COMBINING DIAERESIS) -- on a Windows target system,
        this should be translated to the preferred Unicode normal form
        (composed).

        UA should offer to download the resource as "foo-ä.html".
        """
        header_checker.check_filename(
            "attachment; filename*=UTF-8''foo-a%cc%88.html",
            'foo-ä.html')

    def test_attwithfn2231utf8_bad(self, header_checker):
        """'attachment', specifying a filename of foo-ä-€.html.

        Using RFC2231 encoded UTF-8, but declaring ISO-8859-1.

        The octet %82 does not represent a valid ISO-8859-1 code point, so the
        UA should really ignore the parameter.
        """
        header_checker.check_ignored("attachment; "
                                     "iso-8859-1''foo-%c3%a4-%e2%82%ac.html")

    def test_attwithfn2231iso_bad(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Using RFC2231 encoded ISO-8859-1, but declaring UTF-8.

        The octet %E4 does not represent a valid UTF-8 octet sequence, so the
        UA should really ignore the parameter.
        """
        header_checker.check_ignored(
            "attachment; filename*=utf-8''foo-%E4.html")

    def test_attwithfn2231ws1(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Using RFC2231 encoded UTF-8, with whitespace before "*="
        The parameter is invalid, thus should be ignored.
        """
        header_checker.check_ignored(
            "attachment; filename *=UTF-8''foo-%c3%a4.html")

    def test_attwithfn2231ws2(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Using RFC2231 encoded UTF-8, with whitespace after "*=".

        UA should offer to download the resource as "foo-ä.html".
        """
        header_checker.check_filename(
            "attachment; filename*= UTF-8''foo-%c3%a4.html",
            'foo-ä.html')

    def test_attwithfn2231ws3(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Using RFC2231 encoded UTF-8, with whitespace inside "* ="
        UA should offer to download the resource as "foo-ä.html".
        """
        header_checker.check_filename(
            "attachment; filename* =UTF-8''foo-%c3%a4.html",
            'foo-ä.html')

    def test_attwithfn2231quot(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Using RFC2231 encoded UTF-8, with double quotes around the parameter
        value.

        The parameter is invalid, thus should be ignored.
        """
        header_checker.check_ignored(
            "attachment; filename*=\"UTF-8''foo-%c3%a4.html\"")

    def test_attwithfn2231quot2(self, header_checker):
        """'attachment', specifying a filename of foo bar.html.

        Using "filename*", but missing character encoding and language (this
        replicates a bug in MS Exchange 2010, see Mozilla Bug 704989).

        The parameter is invalid, thus should be ignored.
        """
        header_checker.check_ignored('attachment; filename*="foo%20bar.html"')

    def test_attwithfn2231singleqmissing(self, header_checker):
        """'attachment', specifying a filename of foo-ä.html.

        Using RFC2231 encoded UTF-8, but a single quote is missing.
        The parameter is invalid, thus should be ignored.
        """
        header_checker.check_ignored(
            "attachment; filename*=UTF-8'foo-%c3%a4.html")

    def test_attwithfn2231nbadpct1(self, header_checker):
        """'attachment', specifying a filename of foo%.

        Using RFC2231 encoded UTF-8, with a single "%" at the end.
        The parameter is invalid, thus should be ignored.
        """
        header_checker.check_ignored("attachment; filename*=UTF-8''foo%")

    def test_attwithfn2231nbadpct2(self, header_checker):
        """'attachment', specifying a filename of f%oo.html.

        Using RFC2231 encoded UTF-8, with a "%" not starting a percent-escape.
        The parameter is invalid, thus should be ignored.
        """
        header_checker.check_ignored("attachment; filename*=UTF-8''f%oo.html")

    def test_attwithfn2231dpct(self, header_checker):
        """'attachment', specifying a filename of A-%41.html.

        Using RFC2231 encoded UTF-8.
        """
        header_checker.check_filename(
            "attachment; filename*=UTF-8''A-%2541.html",
            'A-%41.html')

    @pytest.mark.posix
    def test_attwithfn2231abspathdisguised_unix(self, header_checker):
        r"""'attachment', specifying a filename of \foo.html.

        Using RFC2231 encoded UTF-8.
        """
        header_checker.check_filename(
            "attachment; filename*=UTF-8''%5cfoo.html",
            r'\foo.html')

    @pytest.mark.windows
    def test_attwithfn2231abspathdisguised_win(self, header_checker):
        r"""'attachment', specifying a filename of \foo.html.

        Using RFC2231 encoded UTF-8.
        """
        header_checker.check_filename(
            "attachment; filename*=UTF-8''%5cfoo.html",
            r'foo.html')


# Note we do not test the "RFC2231 Encoding: Continuations (optional)" section


class TestEncodingFallback:

    """Test the same parameter both in traditional and extended format.

    This tests how the UA behaves when the same parameter name appears
    both in traditional and RFC 2231/5987 extended format.
    """

    def test_attfnboth(self, header_checker):
        """'attachment', specifying a filename in both formats.

        foo-ae.html in the traditional format, and foo-ä.html in RFC2231
        format.

        Section 4.2 of RFC 5987 and Section 4.3 of RFC 6266 suggest that the
        RFC 2231/5987 encoded parameter ("filename*") should take precedence
        when understood.
        """
        header_checker.check_filename("attachment; filename=\"foo-ae.html\"; "
                                      "filename*=UTF-8''foo-%c3%a4.html",
                                      'foo-ä.html')

    def test_attfnboth2(self, header_checker):
        """'attachment', specifying a filename in both formats.

        foo-ae.html in the traditional format, and foo-ä.html in RFC2231
        format.

        Section 4.2 of RFC 5987 and Section 4.3 of RFC 6266 suggest that the
        RFC 2231/5987 encoded parameter ("filename*") should take precedence
        when understood.
        """
        header_checker.check_filename(
            "attachment; filename*=UTF-8''foo-%c3%a4.html; "
            "filename=\"foo-ae.html\"", 'foo-ä.html')

    def test_attfnboth3(self, header_checker):
        """'attachment', specifying an ambiguous filename.

        currency-sign=¤ in the simple RFC2231/5987 format, and euro-sign=€ in
        RFC2231-with-continuations format.

        A UA that supports could pick either, or ignore both because of the
        ambiguity.
        """
        header_checker.check_ignored(
            "attachment; filename*0*=ISO-8859-15''euro-sign%3d%a4; "
            "filename*=ISO-8859-1''currency-sign%3d%a4")

    def test_attnewandfn(self, header_checker):
        """'attachment', specifying a new parameter "foobar".

        Plus a filename of foo.html in the traditional format.

        "foobar" should be ignored, thus "foo.html" be used as filename (this
        tests whether the UA properly skips unknown parameters).
        """
        header_checker.check_filename(
            'attachment; foobar=x; filename="foo.html"',
            'foo.html')


class TestRFC2047Encoding:

    """Test RFC 2047 style encoding.

    Note that according to Section 5 of RFC 2047, this encoding does not apply
    here: An 'encoded-word' MUST NOT appear within a 'quoted-string'., and An
    'encoded-word' MUST NOT be used in parameter of a MIME Content-Type or
    Content-Disposition field, or in any structured field body except within a
    'comment' or 'phrase'.

    Therefore, these tests are only be present in order to check whether the UA
    by mistake tries to implement RFC 2047.

    Note that for some bizarre reason, some Web sites, such as GMail, use this
    encoding despite historically it was only implemented in Mozilla browsers,
    which do support the RFC2231 encoding as well.
    """

    def test_attrfc2047token(self, header_checker):
        """Uses RFC 2047 style encoded word.

        "=" is invalid inside the token production, so this is invalid.
        """
        header_checker.check_ignored(
            'attachment; filename==?ISO-8859-1?Q?foo-=E4.html?=')

    def test_attrfc2047quoted(self, header_checker):
        """Uses RFC 2047 style encoded word.

        Using the quoted-string production.
        """
        header_checker.check_filename(
            'attachment; filename="=?ISO-8859-1?Q?foo-=E4.html?="',
            '=?ISO-8859-1?Q?foo-=E4.html?=')
