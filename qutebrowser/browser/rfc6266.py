# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""pyPEG parsing for the RFC 6266 (Content-Disposition) header."""

import collections
import urllib.parse
import string
import re

import pypeg2 as peg

from qutebrowser.utils import utils


class UniqueNamespace(peg.Namespace):

    """A pyPEG2 namespace which prevents setting a value twice."""

    def __setitem__(self, key, value):
        if key in self:
            raise DuplicateParamError(key)
        super().__setitem__(key, value)


# RFC 2616
separator_chars = "()<>@,;:\\\"/[]?={} \t"
ctl_chars = ''.join(chr(i) for i in range(32)) + chr(127)
nontoken_chars = separator_chars + ctl_chars


# RFC 5987
attr_chars_nonalnum = '!#$&+-.^_`|~'
attr_chars = string.ascii_letters + string.digits + attr_chars_nonalnum


# RFC 5987 gives this alternative construction of the token character class
token_chars = attr_chars + "*'%"


# Definitions from https://tools.ietf.org/html/rfc2616#section-2.2
# token was redefined from attr_chars to avoid using AnyBut,
# which might include non-ascii octets.
token_re = '[{}]+'.format(re.escape(token_chars))


class Token(str):

    """A token (RFC 2616, Section 2.2)."""

    grammar = re.compile(token_re)


# RFC 2616 says some linear whitespace (LWS) is in fact allowed in text
# and qdtext; however it also mentions folding that whitespace into
# a single SP (which isn't in CTL) before interpretation.
# Assume the caller already that folding when parsing headers.

# NOTE: qdtext also allows non-ascii, which we choose to parse
# as ISO-8859-1; rejecting it entirely would also be permitted.
# Some broken browsers attempt encoding-sniffing, which is broken
# because the spec only allows iso, and because encoding-sniffing
# can mangle valid values.
# Everything else in this grammar (including RFC 5987 ext values)
# is in an ascii-safe encoding.

qdtext_re = r'[^"{}]'.format(re.escape(ctl_chars))
quoted_pair_re = r'\\[{}]'.format(re.escape(
    ''.join(chr(i) for i in range(128))))


class QuotedString(str):

    """A quoted string (RFC 2616, Section 2.2)."""

    grammar = re.compile(r'"({}|{})+"'.format(quoted_pair_re, qdtext_re))

    def __str__(self):
        s = super().__str__()
        s = s[1:-1]  # remove quotes
        s = re.sub(r'\\(.)', r'\1', s)  # drop backslashes
        return s


class Value(str):

    """A value. (RFC 2616, Section 3.6)."""

    grammar = [re.compile(token_re), QuotedString]


class Charset(str):

    """A charset (RFC5987, Section 3.2.1)."""

    # Other charsets are forbidden, the spec reserves them
    # for future evolutions.
    grammar = re.compile('UTF-8|ISO-8859-1', re.I)


class Language(str):

    """A language-tag (RFC 5646, Section 2.1).

    FIXME: This grammar is not 100% correct yet.
    https://github.com/The-Compiler/qutebrowser/issues/105
    """

    grammar = re.compile('[A-Za-z0-9-]+')


attr_char_re = '[{}]'.format(re.escape(attr_chars))
hex_digit_re = '%[' + string.hexdigits + ']{2}'


class ValueChars(str):

    """A value of an attribute.

    FIXME: Can we merge this with Value?
    https://github.com/The-Compiler/qutebrowser/issues/105
    """

    grammar = re.compile('({}|{})*'.format(attr_char_re, hex_digit_re))


class ExtValue(peg.List):

    """An ext-value of an attribute (RFC 5987, Section 3.2)."""

    grammar = peg.contiguous(Charset, "'", peg.optional(Language), "'",
                             ValueChars)


class ExtToken(peg.Symbol):

    """A token introducing an extended value (RFC 6266, Section 4.1)."""

    regex = re.compile(token_re + r'\*')

    def __str__(self):
        return super().__str__().lower()


class NoExtToken(peg.Symbol):

    """A token introducing a normal value (RFC 6266, Section 4.1)."""

    regex = re.compile(token_re + r'(?<!\*)')

    def __str__(self):
        return super().__str__().lower()


class DispositionParm(str):

    """A parameter for the Disposition-Type header (RFC6266, Section 4.1)."""

    grammar = peg.attr('name', NoExtToken), '=', Value


class ExtDispositionParm:

    """An extended parameter (RFC6266, Section 4.1)."""

    grammar = peg.attr('name', ExtToken), '=', ExtValue

    def __init__(self, value, name=None):
        self.name = name
        self.value = value


class DispositionType(peg.List):

    """The disposition type (RFC6266, Section 4.1)."""

    grammar = [re.compile('(inline|attachment)', re.I), Token]


class DispositionParmList(UniqueNamespace):

    """A list of disposition parameters (RFC6266, Section 4.1)."""

    grammar = peg.maybe_some(';', [ExtDispositionParm, DispositionParm])


class ContentDispositionValue:

    """A complete Content-Disposition value (RFC 6266, Section 4.1)."""

    # Allows nonconformant final semicolon
    # I've seen it in the wild, and browsers accept it
    # http://greenbytes.de/tech/tc2231/#attwithasciifilenamenqs
    grammar = (peg.attr('dtype', DispositionType),
               peg.attr('params', DispositionParmList),
               peg.optional(';'))


LangTagged = collections.namedtuple('LangTagged', ['string', 'langtag'])


class Error(Exception):

    """Base class for RFC6266 errors."""


class DuplicateParamError(Error):

    """Exception raised when a parameter has been given twice."""


class InvalidISO8859Error(Error):

    """Exception raised when a byte is invalid in ISO-8859-1."""


class _ContentDisposition:

    """Records various indications and hints about content disposition.

    These can be used to know if a file should be downloaded or
    displayed directly, and to hint what filename it should have
    in the download case.
    """

    def __init__(self, disposition, assocs):
        """Used internally after parsing the header."""
        assert len(disposition) == 1
        self.disposition = disposition[0]
        self.assocs = dict(assocs)  # So we can change values
        if 'filename*' in self.assocs:
            param = self.assocs['filename*']
            assert isinstance(param, ExtDispositionParm)
            self.assocs['filename*'] = parse_ext_value(param.value).string

    def filename(self):
        """The filename from the Content-Disposition header or None.

        On safety:

        This property records the intent of the sender.

        You shouldn't use this sender-controlled value as a filesystem path, it
        can be insecure. Serving files with this filename can be dangerous as
        well, due to a certain browser using the part after the dot for
        mime-sniffing.  Saving it to a database is fine by itself though.
        """
        if 'filename*' in self.assocs:
            return self.assocs['filename*']
        elif 'filename' in self.assocs:
            # XXX Reject non-ascii (parsed via qdtext) here?
            return self.assocs['filename']

    def is_inline(self):
        """Return if the file should be handled inline.

        If not, and unless your application supports other dispositions
        than the standard inline and attachment, it should be handled
        as an attachment.
        """
        return self.disposition.lower() == 'inline'

    def __repr__(self):
        return utils.get_repr(self, constructor=True,
                              disposition=self.disposition, assocs=self.assocs)


def normalize_ws(text):
    """Do LWS (linear whitespace) folding."""
    return ' '.join(text.split())


def parse_headers(content_disposition):
    """Build a _ContentDisposition from header values."""
    # https://bitbucket.org/logilab/pylint/issue/492/
    # pylint: disable=no-member

    # We allow non-ascii here (it will only be parsed inside of qdtext, and
    # rejected by the grammar if it appears in other places), although parsing
    # it can be ambiguous.  Parsing it ensures that a non-ambiguous filename*
    # value won't get dismissed because of an unrelated ambiguity in the
    # filename parameter. But it does mean we occasionally give
    # less-than-certain values for some legacy senders.
    content_disposition = content_disposition.decode('iso-8859-1')
    # Our parsing is relaxed in these regards:
    # - The grammar allows a final ';' in the header;
    # - We do LWS-folding, and possibly normalise other broken
    #   whitespace, instead of rejecting non-lws-safe text.
    # XXX Would prefer to accept only the quoted whitespace
    # case, rather than normalising everything.
    content_disposition = normalize_ws(content_disposition)
    parsed = peg.parse(content_disposition, ContentDispositionValue)
    return _ContentDisposition(disposition=parsed.dtype, assocs=parsed.params)


def parse_ext_value(val):
    """Parse the value of an extended attribute."""
    if len(val) == 3:
        charset, langtag, coded = val
    else:
        charset, coded = val
        langtag = None
    decoded = urllib.parse.unquote(coded, charset, errors='strict')
    if charset == 'iso-8859-1':
        # Fail if the filename contains an invalid ISO-8859-1 char
        for c in decoded:
            if 0x7F <= ord(c) <= 0x9F:
                raise InvalidISO8859Error(c)
    return LangTagged(decoded, langtag)
