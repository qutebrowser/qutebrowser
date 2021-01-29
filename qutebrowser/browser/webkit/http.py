# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Parsing functions for various HTTP headers."""

import email.headerregistry
import email.errors
import dataclasses
import os.path
from typing import Type

from PyQt5.QtNetwork import QNetworkRequest

from qutebrowser.utils import log, utils


class ContentDispositionError(Exception):

    """Base class for RFC6266 errors."""


@dataclasses.dataclass
class DefectWrapper:

    """Wrapper around a email.error for comparison."""

    error_class: Type[email.errors.MessageDefect]
    line: str

    def __eq__(self, other):
        return (
            isinstance(other, self.error_class)
            and other.line == self.line  # type: ignore[attr-defined]
        )


class ContentDisposition:

    """Records various indications and hints about content disposition.

    These can be used to know if a file should be downloaded or
    displayed directly, and to hint what filename it should have
    in the download case.
    """

    # Ignoring this defect fixes the attfnboth2 test case. It does *not* fix attfnboth
    # one which has a slightly different wording ("duplicate(s) ignored" instead of
    # "duplicate ignored"), because even if we did ignore that one, it still wouldn't
    # work properly...
    _IGNORED_DEFECT = DefectWrapper(
        email.errors.InvalidHeaderDefect,  # type: ignore[attr-defined]
        'duplicate parameter name; duplicate ignored'
    )

    def __init__(self, disposition, params):
        """Used internally after parsing the header."""
        self.disposition = disposition
        self.params = params
        assert 'filename*' not in self.params  # Handled by headerregistry

    @classmethod
    def parse(cls, value):
        """Build a _ContentDisposition from header values."""
        # We allow non-ascii here (it will only be parsed inside of qdtext, and
        # rejected by the grammar if it appears in other places), although parsing
        # it can be ambiguous.  Parsing it ensures that a non-ambiguous filename*
        # value won't get dismissed because of an unrelated ambiguity in the
        # filename parameter. But it does mean we occasionally give
        # less-than-certain values for some legacy senders.
        decoded = value.decode('iso-8859-1')

        reg = email.headerregistry.HeaderRegistry()
        try:
            parsed = reg('Content-Disposition', decoded)
        except IndexError:  # pragma: no cover
            # WORKAROUND for https://bugs.python.org/issue37491
            # Fixed in Python 3.7.5 and 3.8.0.
            raise ContentDispositionError("Missing closing quote character")
        except ValueError:  # pragma: no cover
            # WORKAROUND for https://bugs.python.org/issue42946
            raise ContentDispositionError("Non-ASCII digit")

        if parsed.defects:
            defects = list(parsed.defects)
            if defects != [cls._IGNORED_DEFECT]:  # type: ignore[comparison-overlap]
                raise ContentDispositionError(defects)

        assert isinstance(parsed, email.headerregistry.ContentDispositionHeader), parsed
        return cls(disposition=parsed.content_disposition, params=parsed.params)

    def filename(self):
        """The filename from the Content-Disposition header or None.

        On safety:

        This property records the intent of the sender.

        You shouldn't use this sender-controlled value as a filesystem path, it
        can be insecure. Serving files with this filename can be dangerous as
        well, due to a certain browser using the part after the dot for
        mime-sniffing.  Saving it to a database is fine by itself though.
        """
        return self.params.get('filename')

    def is_inline(self):
        """Return if the file should be handled inline.

        If not, and unless your application supports other dispositions
        than the standard inline and attachment, it should be handled
        as an attachment.
        """
        return self.disposition in {None, 'inline'}

    def __repr__(self):
        return utils.get_repr(self, constructor=True,
                              disposition=self.disposition, params=self.params)


def parse_content_disposition(reply):
    """Parse a content_disposition header.

    Args:
        reply: The QNetworkReply to get a filename for.

    Return:
        A (is_inline, filename) tuple.
    """
    is_inline = True
    filename = None
    content_disposition_header = 'Content-Disposition'.encode('iso-8859-1')
    # First check if the Content-Disposition header has a filename
    # attribute.
    if reply.hasRawHeader(content_disposition_header):
        # We use the unsafe variant of the filename as we sanitize it via
        # os.path.basename later.
        try:
            value = bytes(reply.rawHeader(content_disposition_header))
            log.network.debug("Parsing Content-Disposition: {value!r}")
            content_disposition = ContentDisposition.parse(value)
            filename = content_disposition.filename()
        except ContentDispositionError as e:
            log.network.error(f"Error while parsing filename: {e}")
        else:
            is_inline = content_disposition.is_inline()
    # Then try to get filename from url
    if not filename:
        filename = reply.url().path().rstrip('/')
    # If that fails as well, use a fallback
    if not filename:
        filename = 'qutebrowser-download'
    return is_inline, os.path.basename(filename)


def parse_content_type(reply):
    """Parse a Content-Type header.

    The parsing done here is very cheap, as we really only want to get the
    Mimetype. Parameters aren't parsed specially.

    Args:
        reply: The QNetworkReply to handle.

    Return:
        A [mimetype, rest] list, or [None, None] if unset.
        Rest can be None.
    """
    content_type = reply.header(QNetworkRequest.ContentTypeHeader)
    if content_type is None:
        return [None, None]
    if ';' in content_type:
        ret = content_type.split(';', maxsplit=1)
    else:
        ret = [content_type, None]
    ret[0] = ret[0].strip()
    return ret
