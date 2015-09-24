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

import collections
import uuid
from email import policy, generator, encoders
from email.mime import multipart

from PyQt5.QtCore import QUrl

from qutebrowser.browser import webelem
from qutebrowser.utils import log, objreg, message


_File = collections.namedtuple('_File',
                               ['content', 'content_type', 'content_location',
                                'transfer_encoding'])


_CSS_URL_PATTERNS = [re.compile(x) for x in [
    r"@import\s+'(?P<url>[^']+)'",
    r'@import\s+"(?P<url>[^"]+)"',
    r'''url\((?P<url>[^'"][^)]*)\)''',
    r'url\("(?P<url>[^"]+)"\)',
    r"url\('(?P<url>[^']+)'\)",
]]


def _get_css_imports(data):
    """Return all assets that are referenced in the given CSS document.
    The returned URLs are relative to the stylesheet's URL.
    Args:
        data: The content of the stylesheet to scan as string.
    """
    urls = []
    for pattern in _CSS_URL_PATTERNS:
        for match in pattern.finditer(data):
            url = match.group("url")
            if url:
                urls.append(url)
    return urls


MHTMLPolicy = policy.default.clone(linesep='\r\n', max_line_length=0)


E_BASE64 = encoders.encode_base64
"""Encode the file using base64 encoding"""

E_QUOPRI = encoders.encode_quopri
"""Encode the file using MIME quoted-printable encoding."""


class MHTMLWriter():

    """A class for outputting multiple files to a MHTML document.

    Attributes:
        root_content: The root content as bytes.
        content_location: The url of the page as str.
        content_type: The MIME-type of the root content as str.
        _files: Mapping of location->_File struct.
    """

    def __init__(self, root_content, content_location, content_type):
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
        msg = multipart.MIMEMultipart('related',
                                      '---=_qute-{}'.format(uuid.uuid4()))

        root = self._create_root_file()
        msg.attach(root)

        for _, file_data in sorted(self._files.items()):
            msg.attach(self._create_file(file_data))

        gen = generator.BytesGenerator(fp, policy=MHTMLPolicy)
        gen.flatten(msg)

    def _create_root_file(self):
        """Return the root document as MIMEMultipart."""
        root_file = _File(
            content=self.root_content, content_type=self.content_type,
            content_location=self.content_location, transfer_encoding=E_QUOPRI,
        )
        return self._create_file(root_file)

    def _create_file(self, f):
        """Return the single given file as MIMEMultipart."""
        msg = multipart.MIMEMultipart()
        msg['Content-Location'] = f.content_location
        # Get rid of the default type multipart/mixed
        del msg['Content-Type']
        if f.content_type:
            msg.set_type(f.content_type)
        msg.set_payload(f.content)
        f.transfer_encoding(msg)
        return msg


class _Downloader():

    """A class to download whole websites.

    Attributes:
        web_view: The QWebView which contains the website that will be saved.
        dest: Destination filename.
        writer: The MHTMLWriter object which is used to save the page.
        loaded_urls: A set of QUrls of finished asset downloads.
        pending_downloads: A set of unfinished (url, DownloadItem) tuples.
        _finished: A flag indicating if the file has already been written.
        _used: A flag indicating if the downloader has already been used.
    """

    def __init__(self, web_view, dest):
        self.web_view = web_view
        self.dest = dest
        self.writer = None
        self.loaded_urls = {web_view.url()}
        self.pending_downloads = set()
        self._finished = False
        self._used = False

    def run(self):
        """Download and save the page.

        The object must not be reused, you should create a new one if
        you want to download another page.
        """
        if self._used:
            raise ValueError("Downloader already used")
        self._used = True
        web_url = self.web_view.url()
        web_frame = self.web_view.page().mainFrame()

        self.writer = MHTMLWriter(
            web_frame.toHtml().encode('utf-8'),
            content_location=web_url.toString(),
            # I've found no way of getting the content type of a QWebView, but
            # since we're using .toHtml, it's probably safe to say that the
            # content-type is HTML
            content_type='text/html; charset="UTF-8"',
        )
        # Currently only downloading <link> (stylesheets), <script>
        # (javascript) and <img> (image) elements.
        elements = web_frame.findAllElements('link, script, img')

        for element in elements:
            element = webelem.WebElementWrapper(element)
            if 'src' in element:
                element_url = element['src']
            elif 'href' in element:
                element_url = element['href']
            else:
                # Might be a local <script> tag or something else
                continue
            absolute_url = web_url.resolved(QUrl(element_url))
            self.fetch_url(absolute_url)

        styles = web_frame.findAllElements('style')
        for style in styles:
            style = webelem.WebElementWrapper(style)
            if 'type' in style and style['type'] != 'text/css':
                continue
            for element_url in _get_css_imports(str(style)):
                self.fetch_url(web_url.resolved(QUrl(element_url)))

        # Search for references in inline styles
        for element in web_frame.findAllElements('[style]'):
            element = webelem.WebElementWrapper(element)
            style = element['style']
            for element_url in _get_css_imports(style):
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
        if url.scheme() == 'data':
            return
        # Prevent loading an asset twice
        if url in self.loaded_urls:
            return
        self.loaded_urls.add(url)

        log.downloads.debug("loading asset at %s", url)

        download_manager = objreg.get('download-manager', scope='window',
                                      window='current')
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
        mime = item.raw_headers.get(b'Content-Type', b'')

        # Note that this decoding always works and doesn't produce errors
        # RFC 7230 (https://tools.ietf.org/html/rfc7230) states:
        # Historically, HTTP has allowed field content with text in the
        # ISO-8859-1 charset [ISO-8859-1], supporting other charsets only
        # through use of [RFC2047] encoding.  In practice, most HTTP header
        # field values use only a subset of the US-ASCII charset [USASCII].
        # Newly defined header fields SHOULD limit their field values to
        # US-ASCII octets.  A recipient SHOULD treat other octets in field
        # content (obs-text) as opaque data.
        mime = mime.decode('iso-8859-1')

        if mime.lower() == 'text/css':
            # We can't always assume that CSS files are UTF-8, but CSS files
            # shouldn't contain many non-ASCII characters anyway (in most
            # cases). Using "ignore" lets us decode the file even if it's
            # invalid UTF-8 data.
            # The file written to the MHTML file won't be modified by this
            # decoding, since there we're taking the original bytestream.
            try:
                css_string = item.fileobj.getvalue().decode('utf-8')
            except UnicodeDecodeError:
                log.downloads.warning("Invalid UTF-8 data in %s", url)
                css_string = item.fileobj.getvalue().decode('utf-8', 'ignore')
            import_urls = _get_css_imports(css_string)
            for import_url in import_urls:
                absolute_url = url.resolved(QUrl(import_url))
                self.fetch_url(absolute_url)

        encode = E_QUOPRI if mime.startswith('text/') else E_BASE64
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
            log.downloads.debug("Oops! Download already gone: %s", item)
            return
        item.fileobj.actual_close()
        self.writer.add_file(url.toString(), b'')
        if self.pending_downloads:
            return
        self.finish_file()

    def finish_file(self):
        """Save the file to the filename given in __init__."""
        if self._finished:
            log.downloads.debug("finish_file called twice, ignored!")
            return
        self._finished = True
        log.downloads.debug("All assets downloaded, ready to finish off!")
        with open(self.dest, 'wb') as file_output:
            self.writer.write_to(file_output)
        message.info('current', "Page saved as {}".format(self.dest))

    def collect_zombies(self):
        """Collect done downloads and add their data to the MHTML file.

        This is needed if a download finishes before attaching its
        finished signal.
        """
        items = set((url, item) for url, item in self.pending_downloads
                    if item.done)
        log.downloads.debug("Zombie downloads: %s", items)
        for url, item in items:
            self.finished(url, item)


class _NoCloseBytesIO(io.BytesIO):  # pylint: disable=no-init

    """BytesIO that can't be .closed().

    This is needed to prevent the DownloadManager from closing the stream, thus
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
    web_view = objreg.get('webview', scope='tab', tab='current')
    loader = _Downloader(web_view, dest)
    loader.run()
