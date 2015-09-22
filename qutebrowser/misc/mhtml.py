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

"""Utils for writing a MHTML file."""

import functools
import io
import os

from collections import namedtuple
from base64 import b64encode
from urllib.parse import urljoin
from uuid import uuid4

from PyQt5.QtCore import QUrl

from qutebrowser.utils import log, objreg, message


_File = namedtuple("_File",
                   "content content_type content_location transfer_encoding")


def _chunked_base64(data, maxlen=76, linesep=b"\r\n"):
    """Just like b64encode, except that it breaks long lines.

    Args:
        maxlen: Maximum length of a line, not including the line separator.
        linesep: Line separator to use as bytes.
    """
    encoded = b64encode(data)
    result = []
    for i in range(0, len(encoded), maxlen):
        result.append(encoded[i:i + maxlen])
    return linesep.join(result)


def _rn_quopri(data):
    """Return a quoted-printable representation of data."""
    # See RFC 2045 https://tools.ietf.org/html/rfc2045#section-6.7
    # The stdlib version in the quopri module has inconsistencies with line
    # endings and breaks up character escapes over multiple lines, which isn't
    # understood by qute and leads to jumbled text
    maxlen = 76
    whitespace = {ord(b"\t"), ord(b" ")}
    output = []
    current_line = b""
    for byte in data:
        # Literal representation according to (2) and (3)
        if (ord(b"!") <= byte <= ord(b"<") or ord(b">") <= byte <= ord(b"~")
                or byte in whitespace):
            current_line += bytes([byte])
        else:
            current_line += b"=" + "{:02X}".format(byte).encode("ascii")
        if len(current_line) >= maxlen:
            # We need to account for the = character
            split = [current_line[:maxlen - 1], current_line[maxlen - 1:]]
            quoted_pos = split[0].rfind(b"=")
            if quoted_pos + 2 >= maxlen - 1:
                split[0], token = split[0][:quoted_pos], split[0][quoted_pos:]
                split[1] = token + split[1]
            current_line = split[1]
            output.append(split[0] + b"=")
    output.append(current_line)
    return b"\r\n".join(output)


E_NONE = (None, lambda x: x)
"""No transfer encoding, copy the bytes from input to output"""

E_BASE64 = ("base64", _chunked_base64)
"""Encode the file using base64 encoding"""

E_QUOPRI = ("quoted-printable", _rn_quopri)
"""Encode the file using MIME quoted-printable encoding."""


class MHTMLWriter(object):

    """A class for outputting multiple files to a MHTML document."""

    BOUNDARY = b"---qute-mhtml-" + str(uuid4()).encode("ascii")

    def __init__(self, root_content=None, content_location=None,
                 content_type=None):
        self.root_content = root_content
        self.content_location = content_location
        self.content_type = content_type

        self._files = {}

    def add_file(self, location, content, content_type=None,
                 transfer_encoding=E_QUOPRI):
        """Add a file to the given MHTML collection.

        Args:
            location: The original location (URL) of the file.
            content: The binary content of the file.
            content_type: The MIME-type of the content (if available)
            transfer_encoding: The transfer encoding to use for this file.
        """
        self._files[location] = _File(
            content=content, content_type=content_type,
            content_location=location, transfer_encoding=transfer_encoding,
        )

    def remove_file(self, location):
        """Remove a file.

        Args:
            location: The URL that identifies the file.
        """
        del self._files[location]

    def write_to(self, fp):
        """Output the MHTML file to the given file-like object.

        Args:
            fp: The file-object, openend in "wb" mode.
        """
        self._output_header(fp)
        self._output_root_file(fp)
        for file_data in self._files.values():
            self._output_file(fp, file_data)
        fp.write(b"\r\n--")
        fp.write(self.BOUNDARY)
        fp.write(b"--")

    def _output_header(self, fp):
        """Output only the header to the given fileobject."""
        if self.content_location is None:
            raise ValueError("content_location must be set")
        if self.content_type is None:
            raise ValueError("content_type must be set for the root document")

        fp.write(b"Content-Location: ")
        fp.write(self.content_location.encode("utf-8"))
        fp.write(b'\r\nContent-Type: multipart/related;boundary="')
        fp.write(self.BOUNDARY)
        fp.write(b'";type="')
        fp.write(self.content_type.encode("utf-8"))
        fp.write(b'"\r\n\r\n')

    def _output_root_file(self, fp):
        """Output the root document to the fileobject."""
        root_file = _File(
            content=self.root_content, content_type=self.content_type,
            content_location=self.content_location, transfer_encoding=E_QUOPRI,
        )
        self._output_file(fp, root_file)

    def _output_file(self, fp, file_struct):
        """Output the single given file to the fileobject."""
        fp.write(b"--")
        fp.write(self.BOUNDARY)
        fp.write(b"\r\nContent-Location: ")
        fp.write(file_struct.content_location.encode("utf-8"))
        if file_struct.content_type is not None:
            fp.write(b"\r\nContent-Type: ")
            fp.write(file_struct.content_type.encode("utf-8"))
        encoding_name, encoding_func = file_struct.transfer_encoding
        if encoding_name:
            fp.write(b"\r\nContent-Transfer-Encoding: ")
            fp.write(encoding_name.encode("utf-8"))
        fp.write(b"\r\n\r\n")
        fp.write(encoding_func(file_struct.content))
        fp.write(b"\r\n\r\n")


class _Downloader(object):

    """A class to download whole websites."""

    def __init__(self, web_view, dest):
        self.web_view = web_view
        self.dest = dest
        self.writer = MHTMLWriter()
        self.loaded_urls = set()
        self.pending_downloads = set()

    def run(self):
        """Download and save the page.

        The object must not be reused, you should create a new one if
        you want to download another page.
        """
        download_manager = objreg.get("download-manager", scope="window",
                                      window="current")
        web_url_str = self.web_view.url().toString()
        web_frame = self.web_view.page().mainFrame()

        self.writer.root_content = web_frame.toHtml().encode("utf-8")
        self.writer.content_location = web_url_str
        # I've found no way of getting the content type of a QWebView, but
        # since we're using .toHtml, it's probably safe to say that the
        # content-type is HTML
        self.writer.content_type = 'text/html; charset="UTF-8"'
        # Currently only downloading <link> (stylesheets), <script>
        # (javascript) and <img> (image) elements.
        elements = (web_frame.findAllElements("link") +
                    web_frame.findAllElements("script") +
                    web_frame.findAllElements("img"))

        for element in elements:
            element_url = element.attribute("src")
            if not element_url:
                element_url = element.attribute("href")
            if not element_url:
                # Might be a local <script> tag or something else
                continue
            absolute_url = QUrl(urljoin(web_url_str, element_url))
            # Prevent loading an asset twice
            if absolute_url in self.loaded_urls:
                continue
            self.loaded_urls.add(absolute_url)

            log.misc.debug("asset at %s", absolute_url)

            item = download_manager.get(absolute_url, fileobj=io.BytesIO(),
                                        auto_remove=True)
            self.pending_downloads.add(item)
            item.finished.connect(
                functools.partial(self.finished, absolute_url, item))
            item.error.connect(
                functools.partial(self.error, absolute_url, item))
            item.cancelled.connect(
                functools.partial(self.error, absolute_url, item))

    def finished(self, url, item):
        """Callback when a single asset is downloaded.

        Args:
            url: The original url of the asset as QUrl.
            item: The DownloadItem given by the DownloadManager
        """
        self.pending_downloads.remove(item)
        mime = item.raw_headers.get(b"Content-Type", b"")
        mime = mime.decode("ascii", "ignore")
        encode = E_QUOPRI if mime.startswith("text/") else E_BASE64
        self.writer.add_file(url.toString(), item.fileobj.getvalue(), mime,
                             encode)
        if self.pending_downloads:
            return
        self.finish_file()

    def error(self, url, item, *_args):
        """Callback when a download error occurred.

        Args:
            url: The orignal url of the asset as QUrl.
            item: The DownloadItem given by the DownloadManager.
        """
        self.pending_downloads.remove(item)
        self.writer.add_file(url.toString(), b"")
        if self.pending_downloads:
            return
        self.finish_file()

    def finish_file(self):
        """Save the file to the filename given in __init__."""
        log.misc.debug("All assets downloaded, ready to finish off!")
        with open(self.dest, "wb") as file_output:
            self.writer.write_to(file_output)
        message.info("current", "Page saved as {}".format(self.dest), True)


def start_download(dest):
    """Start downloading the current page and all assets to a MHTML file.

    Args:
        dest: The filename where the resulting file should be saved.
    """
    dest = os.path.expanduser(dest)
    web_view = objreg.get("webview", scope="tab", tab="current")
    loader = _Downloader(web_view, dest)
    loader.run()
