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
import re

from collections import namedtuple
from base64 import b64encode
from uuid import uuid4

from PyQt5.QtCore import QUrl

from qutebrowser.utils import log, objreg, message


_File = namedtuple("_File",
                   "content content_type content_location transfer_encoding")


_CSS_URL_PATTERNS = [re.compile(x) for x in [
    rb"@import '(?P<url>[^']+)'",
    rb'@import "(?P<url>[^"]+)"',
    rb'''url\((?P<url>[^'"][^)]*)\)''',
    rb'url\("(?P<url>[^"]+)"\)',
    rb"url\('(?P<url>[^']+)'\)",
]]


def _get_css_imports(data):
    """Return all assets that are referenced in the given CSS document.

    The returned URLs are relative to the stylesheet's URL.

    Args:
        data: The content of the stylesheet to scan.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    urls = []
    for pattern in _CSS_URL_PATTERNS:
        for match in pattern.finditer(data):
            url = match.group("url")
            if url:
                urls.append(url)
    return urls


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

    """A class for outputting multiple files to a MHTML document.

    Attributes:
        root_content: The root content as bytes.
        content_location: The url of the page as str.
        content_type: The MIME-type of the root content as str.
        _files: Mapping of location->_File struct.
    """

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

    """A class to download whole websites.

    Attributes:
        web_view: The QWebView which contains the website that will be saved.
        dest: Destination filename.
        writer: The MHTMLWriter object which is used to save the page.
        loaded_urls: A set of QUrls of finished asset downloads.
        pending_downloads: A set of unfinished (url, DownloadItem) tuples.
        _finished: A flag indicating if the file has already been written.
    """

    def __init__(self, web_view, dest):
        self.web_view = web_view
        self.dest = dest
        self.writer = MHTMLWriter()
        self.loaded_urls = {web_view.url()}
        self.pending_downloads = set()
        self._finished = False

    def run(self):
        """Download and save the page.

        The object must not be reused, you should create a new one if
        you want to download another page.
        """
        web_url = self.web_view.url()
        web_frame = self.web_view.page().mainFrame()

        self.writer.root_content = web_frame.toHtml().encode("utf-8")
        self.writer.content_location = web_url.toString()
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
            absolute_url = web_url.resolved(QUrl(element_url))
            self.fetch_url(absolute_url)

        styles = web_frame.findAllElements("style")
        for style in styles:
            if style.attribute("type", "text/css") != "text/css":
                continue
            for element_url in _get_css_imports(style.toPlainText()):
                element_url = element_url.decode("ascii")
                self.fetch_url(web_url.resolved(QUrl(element_url)))

        # Search for references in inline styles
        for element in web_frame.findAllElements("*"):
            style = element.attribute("style")
            if not style:
                continue
            for element_url in _get_css_imports(style):
                element_url = element_url.decode("ascii")
                self.fetch_url(web_url.resolved(QUrl(element_url)))

        # Shortcut if no assets need to be downloaded, otherwise the file would
        # never be saved. Also might happen if the downloads are fast enough to
        # complete before connecting their finished signal.
        self.collect_zombies()
        if not self.pending_downloads and not self._finished:
            self.finish_file()

    def fetch_url(self, url):
        """Download the given url and add the file to the collection.

        Args:
            url: The file to download as QUrl.
        """
        if url.scheme() == "data":
            return
        # Prevent loading an asset twice
        if url in self.loaded_urls:
            return
        self.loaded_urls.add(url)

        log.misc.debug("loading asset at %s", url)

        download_manager = objreg.get("download-manager", scope="window",
                                      window="current")
        item = download_manager.get(url, fileobj=_NoCloseBytesIO(),
                                    auto_remove=True)
        self.pending_downloads.add((url, item))
        item.finished.connect(
            functools.partial(self.finished, url, item))
        item.error.connect(
            functools.partial(self.error, url, item))
        item.cancelled.connect(
            functools.partial(self.error, url, item))

    def finished(self, url, item):
        """Callback when a single asset is downloaded.

        Args:
            url: The original url of the asset as QUrl.
            item: The DownloadItem given by the DownloadManager
        """
        self.pending_downloads.remove((url, item))
        mime = item.raw_headers.get(b"Content-Type", b"")
        mime = mime.decode("ascii", "ignore")

        if mime.lower() == "text/css":
            import_urls = _get_css_imports(item.fileobj.getvalue())
            for import_url in import_urls:
                import_url = import_url.decode("ascii")
                absolute_url = url.resolved(QUrl(import_url))
                self.fetch_url(absolute_url)

        encode = E_QUOPRI if mime.startswith("text/") else E_BASE64
        self.writer.add_file(url.toString(), item.fileobj.getvalue(), mime,
                             encode)
        item.fileobj.actual_close()
        if self.pending_downloads:
            return
        self.finish_file()

    def error(self, url, item, *_args):
        """Callback when a download error occurred.

        Args:
            url: The orignal url of the asset as QUrl.
            item: The DownloadItem given by the DownloadManager.
        """
        try:
            self.pending_downloads.remove((url, item))
        except KeyError:
            # This might happen if .collect_zombies() calls .finished() and the
            # error handler will be called after .collect_zombies
            log.misc.debug("Oops! Download already gone: %s", item)
            return
        item.fileobj.actual_close()
        self.writer.add_file(url.toString(), b"")
        if self.pending_downloads:
            return
        self.finish_file()

    def finish_file(self):
        """Save the file to the filename given in __init__."""
        if self._finished:
            log.misc.debug("finish_file called twice, ignored!")
            return
        self._finished = True
        log.misc.debug("All assets downloaded, ready to finish off!")
        with open(self.dest, "wb") as file_output:
            self.writer.write_to(file_output)
        message.info("current", "Page saved as {}".format(self.dest), True)

    def collect_zombies(self):
        """Collect done downloads and add their data to the MHTML file.

        This is needed if a download finishes before attaching its
        finished signal.
        """
        items = set((url, item) for url, item in self.pending_downloads
                    if item.done)
        log.misc.debug("Zombie downloads: %s", items)
        for url, item in items:
            self.finished(url, item)


class _NoCloseBytesIO(io.BytesIO):

    """BytesIO that can't be .closed()

    This is needed to prevent the downloadmanager from closing the stream, thus
    discarding the data.
    """

    def close(self):
        """Do nothing."""
        pass

    def actual_close(self):
        """Close the stream."""
        super().close()


def start_download(dest):
    """Start downloading the current page and all assets to a MHTML file.

    Args:
        dest: The filename where the resulting file should be saved.
    """
    dest = os.path.expanduser(dest)
    web_view = objreg.get("webview", scope="tab", tab="current")
    loader = _Downloader(web_view, dest)
    loader.run()
