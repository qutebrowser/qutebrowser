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

"""pyPEG parsing for the RFC 6266 (Content-Disposition) header."""

import email.headerregistry

from qutebrowser.utils import utils


class Error(Exception):

    """Base class for RFC6266 errors."""


class _ContentDisposition:

    """Records various indications and hints about content disposition.

    These can be used to know if a file should be downloaded or
    displayed directly, and to hint what filename it should have
    in the download case.
    """

    def __init__(self, disposition, params):
        """Used internally after parsing the header."""
        self.disposition = disposition
        self.params = params
        assert 'filename*' not in self.params  # Handled by headerregistry

    def filename(self):
        """The filename from the Content-Disposition header or None.

        On safety:

        This property records the intent of the sender.

        You shouldn't use this sender-controlled value as a filesystem path, it
        can be insecure. Serving files with this filename can be dangerous as
        well, due to a certain browser using the part after the dot for
        mime-sniffing.  Saving it to a database is fine by itself though.
        """
        # XXX Reject non-ascii (parsed via qdtext) here?
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


def parse_headers(content_disposition):
    """Build a _ContentDisposition from header values."""
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

    if not content_disposition.strip():
        raise Error("Empty value!")

    reg = email.headerregistry.HeaderRegistry()
    parsed = reg('Content-Disposition', content_disposition)

    if parsed.defects:
        raise Error(parsed.defects)

    return _ContentDisposition(disposition=parsed.content_disposition,
                               params=parsed.params)
