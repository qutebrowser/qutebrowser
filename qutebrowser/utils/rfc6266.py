import pypeg2 as peg

import os.path
from collections import namedtuple
import urllib.parse
import string
import re


LangTagged = namedtuple('LangTagged', 'string langtag')


class ContentDisposition:
    """
    Records various indications and hints about content disposition.

    These can be used to know if a file should be downloaded or
    displayed directly, and to hint what filename it should have
    in the download case.
    """

    def __init__(self, disposition='inline', assocs=None, location=None):
        """This constructor is used internally after parsing the header.

        Instances should generally be created from a factory
        function, such as parse_headers and its variants.
        """
        if len(disposition) != 1:
            self.disposition = 'inline'
        else:
            self.disposition = disposition[0]
        self.location = location
        if assocs is None:
            self.assocs = {}
        else:
            # XXX Check that parameters aren't repeated
            self.assocs = assocs

    @property
    def filename_unsafe(self):
        """The filename from the Content-Disposition header.

        If a location was passed at instanciation, the basename
        from that may be used as a fallback. Otherwise, this may
        be the None value.

        On safety:
            This property records the intent of the sender.

            You shouldn't use this sender-controlled value as a filesystem
        path, it can be insecure. Serving files with this filename can be
        dangerous as well, due to a certain browser using the part after the
        dot for mime-sniffing.
        Saving it to a database is fine by itself though.
        """

        if 'filename*' in self.assocs:
            val = self.assocs['filename*']
            assert isinstance(val, ExtDispositionParm)
            return parse_ext_value(val[0]).string
        elif 'filename' in self.assocs:
            # XXX Reject non-ascii (parsed via qdtext) here?
            return self.assocs['filename']
        elif self.location is not None:
            return os.path.basename(self.location_path.rstrip('/'))

    @property
    def is_inline(self):
        """If this property is true, the file should be handled inline.

        Otherwise, and unless your application supports other dispositions
        than the standard inline and attachment, it should be handled
        as an attachment.
        """

        return self.disposition.lower() == 'inline'

    def __repr__(self):
        return 'ContentDisposition(%r, %r, %r)' % (
            self.disposition, self.assocs, self.location)




def percent_decode(string, encoding):
    # unquote doesn't default to strict, fix that
    return urllib.parse.unquote(string, encoding, errors='strict')


def fits_inside_codec(text, codec):
    try:
        text.encode(codec)
    except UnicodeEncodeError:
        return False
    else:
        return True


def ensure_charset(text, encoding):
    if isinstance(text, bytes):
        return text.decode(encoding)
    else:
        assert fits_inside_codec(text, encoding)
        return text


def parse_headers(content_disposition, location=None, relaxed=False):
    """Build a ContentDisposition from header values.
    """

    # We allow non-ascii here (it will only be parsed inside of qdtext, and
    # rejected by the grammar if it appears in other places), although parsing
    # it can be ambiguous.  Parsing it ensures that a non-ambiguous filename*
    # value won't get dismissed because of an unrelated ambiguity in the
    # filename parameter. But it does mean we occasionally give
    # less-than-certain values for some legacy senders.
    content_disposition = ensure_charset(content_disposition, 'iso-8859-1')

    # Check the caller already did LWS-folding (normally done
    # when separating header names and values; RFC 2616 section 2.2
    # says it should be done before interpretation at any rate).
    # Hopefully space still means what it should in iso-8859-1.
    # This check is a bit stronger that LWS folding, it will
    # remove CR and LF even if they aren't part of a CRLF.
    # However http doesn't allow isolated CR and LF in headers outside
    # of LWS.

    # Relaxed has two effects (so far):
    # the grammar allows a final ';' in the header;
    # we do LWS-folding, and possibly normalise other broken
    # whitespace, instead of rejecting non-lws-safe text.
    # XXX Would prefer to accept only the quoted whitespace
    # case, rather than normalising everything.
    content_disposition = normalize_ws(content_disposition)

    try:
        parsed = peg.parse(content_disposition, ContentDispositionValue)
    except SyntaxError:
        return ContentDisposition(location=location)
    return ContentDisposition(
        disposition=parsed.dtype, assocs=parsed.params, location=location)


def parse_ext_value(val):
    charset = val[0]
    if len(val) == 3:
        charset, langtag, coded = val
    else:
        charset, coded = val
        langtag = None
    decoded = percent_decode(coded, encoding=charset)
    return LangTagged(decoded, langtag)


# Currently pyPEG2 doesn't handle case-insensivitity:
# https://bitbucket.org/fdik/pypeg/issue/21/case-insensitive-keywords
class IKeyword(peg.Keyword):
    def parse(self, parser, text, pos):
        m = self.regex.match(text)
        if m:
            if m.group(0).upper() == str(self).upper():
                return text[len(str(self)):], None
            else:
                return text, SyntaxError("expecting " + repr(self))
        else:
            return text, SyntaxError("expecting " + repr(self))


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
# Because of this, this is the only character class to use AnyBut,
# and all the others are defined with Any.

qdtext_re = r'[^"{}]'.format(re.escape(ctl_chars))
quoted_pair_re = r'\\[{}]'.format(re.escape(''.join(chr(i) for i in range(128))))

class QuotedString(str):
    grammar = re.compile(r'"({}|{})+"'.format(quoted_pair_re, qdtext_re))

    def __str__(self):
        s = super().__str__()
        s = s[1:-1]
        s = re.sub(r'\\(.)', r'\1', s)
        return s


class Value(str):
    grammar = [re.compile(token_re), QuotedString]

# Other charsets are forbidden, the spec reserves them
# for future evolutions.
class Charset(str):
    grammar = re.compile('UTF-8|ISO-8859-1', re.I)

class Language(str):
    # XXX See RFC 5646 for the correct definition
    grammar = re.compile('[A-Za-z0-9-]+')

attr_char_re = '[{}]'.format(re.escape(attr_chars))
hex_digit_re = '%[' + string.hexdigits + ']{2}'

class ValueChars(str):
    grammar = re.compile('({}|{})*'.format(attr_char_re, hex_digit_re))

class ExtValue(peg.List):
    grammar = peg.contiguous(Charset, "'", peg.optional(Language), "'", ValueChars)

class ExtToken(peg.Symbol):
    regex = re.compile(token_re + r'\*')

    def __str__(self):
        return super().__str__().lower()

class NoExtToken(peg.Symbol):
    regex = re.compile(token_re + r'(?<!\*)')

    def __str__(self):
        return super().__str__().lower()

class DispositionParm(str):
    grammar = peg.attr('name', NoExtToken), '=', Value

class ExtDispositionParm(peg.List):
    grammar = peg.attr('name', ExtToken), '=', ExtValue

class DispositionType(peg.List):
    grammar = [re.compile('(inline|attachment)', re.I), Token]

class DispositionParmList(peg.Namespace):
    grammar = peg.maybe_some(';', [ExtDispositionParm, DispositionParm])

class ContentDispositionValue:
    # Allows nonconformant final semicolon
    # I've seen it in the wild, and browsers accept it
    # http://greenbytes.de/tech/tc2231/#attwithasciifilenamenqs
    grammar = (peg.attr('dtype', DispositionType),
               peg.attr('params', DispositionParmList),
               peg.optional(';'))


def is_lws_safe(text):
    return normalize_ws(text) == text


def normalize_ws(text):
    return ' '.join(text.split())


if __name__ == '__main__':
    parsed = peg.parse('attachment; filename="foo.html"', ContentDispositionValue)
    print(parsed.dtype)
    print(parsed.params)
    parsed = peg.parse("attachment; filename*=iso-8859-1''foo-%E4.html", ContentDispositionValue)
    print(parsed.params)
