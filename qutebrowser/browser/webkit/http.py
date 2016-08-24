# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Parsing functions for various HTTP headers."""


import os.path

from qutebrowser.utils import log
from qutebrowser.browser.webkit import rfc6266

from PyQt5.QtNetwork import QNetworkRequest


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
            log.rfc6266.debug("Parsing Content-Disposition: {!r}".format(
                value))
            content_disposition = rfc6266.parse_headers(value)
            filename = content_disposition.filename()
        except (SyntaxError, UnicodeDecodeError, rfc6266.Error):
            log.rfc6266.exception("Error while parsing filename")
        else:
            is_inline = content_disposition.is_inline()
    # Then try to get filename from url
    if not filename:
        path = reply.url().path()
        if path is not None:
            filename = path.rstrip('/')
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
