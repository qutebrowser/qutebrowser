# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015-2018 Daniel Schadt
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

"""Utils for writing an MHTML file."""

import html
import functools
import io
import os
import re
import sys
import uuid
import email.policy
import email.generator
import email.encoders
import email.mime.multipart
import email.message
import quopri
import dataclasses
from typing import MutableMapping, Set, Tuple, Callable

from PyQt5.QtCore import QUrl

from qutebrowser.browser import downloads
from qutebrowser.browser.webkit import webkitelem
from qutebrowser.utils import log, objreg, message, usertypes, utils, urlutils
from qutebrowser.extensions import interceptors


@dataclasses.dataclass
class _File:

    content: bytes
    content_type: str
    content_location: str
    transfer_encoding: Callable[[email.message.Message], None]


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


def _check_rel(element):
    """Return true if the element's rel attribute fits our criteria.

    rel has to contain 'stylesheet' or 'icon'. Also returns True if the rel
    attribute is unset.

    Args:
        element: The WebElementWrapper which should be checked.
    """
    if 'rel' not in element:
        return True
    must_have = {'stylesheet', 'icon'}
    rels = [rel.lower() for rel in element['rel'].split(' ')]
    return any(rel in rels for rel in must_have)


def _encode_quopri_mhtml(msg):
    """Encode the message's payload in quoted-printable.

    Substitute for quopri's default 'encode_quopri' method, which needlessly
    encodes all spaces and tabs, instead of only those at the end on the
    line.

    Args:
        msg: Email message to quote.
    """
    orig = msg.get_payload(decode=True)
    encdata = quopri.encodestring(orig, quotetabs=False)
    msg.set_payload(encdata)
    msg['Content-Transfer-Encoding'] = 'quoted-printable'


MHTMLPolicy = email.policy.default.clone(linesep='\r\n', max_line_length=0)


# Encode the file using base64 encoding.
E_BASE64 = email.encoders.encode_base64


# Encode the file using MIME quoted-printable encoding.
E_QUOPRI = _encode_quopri_mhtml


class MHTMLWriter:

    """A class for outputting multiple files to an MHTML document.

    Attributes:
        root_content: The root content as bytes.
        content_location: The url of the page as str.
        content_type: The MIME-type of the root content as str.
        _files: Mapping of location->_File object.
    """

    def __init__(self, root_content, content_location, content_type):
        self.root_content = root_content
        self.content_location = content_location
        self.content_type = content_type
        self._files: MutableMapping[QUrl, _File] = {}

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

    def write_to(self, fp):
        """Output the MHTML file to the given file-like object.

        Args:
            fp: The file-object, opened in "wb" mode.
        """
        msg = email.mime.multipart.MIMEMultipart(
            'related', '---=_qute-{}'.format(uuid.uuid4()))

        root = self._create_root_file()
        msg.attach(root)

        for _, file_data in sorted(self._files.items()):
            msg.attach(self._create_file(file_data))

        gen = email.generator.BytesGenerator(fp, policy=MHTMLPolicy)
        gen.flatten(msg)

    def _create_root_file(self):
        """Return the root document as MIMEMultipart."""
        root_file = _File(
            content=self.root_content, content_type=self.content_type,
            content_location=self.content_location, transfer_encoding=E_QUOPRI,
        )
        return self._create_file(root_file)

    def _create_file(self, f):
        """Return the single given file as email.message.Message."""
        msg = email.message.Message()
        msg['MIME-Version'] = '1.0'
        msg['Content-Location'] = f.content_location
        if f.content_type:
            msg.set_type(f.content_type)
        msg.set_payload(f.content)
        f.transfer_encoding(msg)
        return msg


_PendingDownloadType = Set[Tuple[QUrl, downloads.AbstractDownloadItem]]


class _Downloader:

    """A class to download whole websites.

    Attributes:
        tab: The AbstractTab which contains the website that will be saved.
        target: DownloadTarget where the file should be downloaded to.
        writer: The MHTMLWriter object which is used to save the page.
        loaded_urls: A set of QUrls of finished asset downloads.
        pending_downloads: A set of unfinished (url, DownloadItem) tuples.
        _finished_file: A flag indicating if the file has already been
                        written.
        _used: A flag indicating if the downloader has already been used.
    """

    def __init__(self, tab, target):
        self.tab = tab
        self.target = target
        self.writer = None
        self.loaded_urls = {tab.url()}
        self.pending_downloads: _PendingDownloadType = set()
        self._finished_file = False
        self._used = False

    def run(self):
        """Download and save the page.

        The object must not be reused, you should create a new one if
        you want to download another page.
        """
        if self._used:
            raise ValueError("Downloader already used")
        self._used = True
        web_url = self.tab.url()

        # FIXME:qtwebengine have a proper API for this
        page = self.tab._widget.page()  # pylint: disable=protected-access
        web_frame = page.mainFrame()

        self.writer = MHTMLWriter(
            web_frame.toHtml().encode('utf-8'),
            content_location=urlutils.encoded_url(web_url),
            # I've found no way of getting the content type of a QWebView, but
            # since we're using .toHtml, it's probably safe to say that the
            # content-type is HTML
            content_type='text/html; charset="UTF-8"',
        )
        # Currently only downloading <link> (stylesheets), <script>
        # (javascript) and <img> (image) elements.
        elements = web_frame.findAllElements('link, script, img')

        for element in elements:
            element = webkitelem.WebKitElement(element, tab=self.tab)
            # Websites are free to set whatever rel=... attribute they want.
            # We just care about stylesheets and icons.
            if not _check_rel(element):
                continue
            if 'src' in element:
                element_url = element['src']
            elif 'href' in element:
                element_url = element['href']
            else:
                # Might be a local <script> tag or something else
                continue
            absolute_url = web_url.resolved(QUrl(element_url))
            self._fetch_url(absolute_url)

        styles = web_frame.findAllElements('style')
        for style in styles:
            style = webkitelem.WebKitElement(style, tab=self.tab)
            # The Mozilla Developer Network says:
            # > type: This attribute defines the styling language as a MIME
            # > type (charset should not be specified). This attribute is
            # > optional and default to text/css if it's missing.
            # https://developer.mozilla.org/en/docs/Web/HTML/Element/style
            if 'type' in style and style['type'] != 'text/css':
                continue
            for element_url in _get_css_imports(str(style)):
                self._fetch_url(web_url.resolved(QUrl(element_url)))

        # Search for references in inline styles
        for element in web_frame.findAllElements('[style]'):
            element = webkitelem.WebKitElement(element, tab=self.tab)
            style = element['style']
            for element_url in _get_css_imports(style):
                self._fetch_url(web_url.resolved(QUrl(element_url)))

        # Shortcut if no assets need to be downloaded, otherwise the file would
        # never be saved. Also might happen if the downloads are fast enough to
        # complete before connecting their finished signal.
        self._collect_zombies()
        if not self.pending_downloads and not self._finished_file:
            self._finish_file()

    def _fetch_url(self, url):
        """Download the given url and add the file to the collection.

        Args:
            url: The file to download as QUrl.
        """
        assert self.writer is not None

        if url.scheme() not in ['http', 'https']:
            return
        # Prevent loading an asset twice
        if url in self.loaded_urls:
            return
        self.loaded_urls.add(url)

        log.downloads.debug("loading asset at {}".format(url))

        # Using the download manager to download host-blocked urls might crash
        # qute, see the comments/discussion on
        # https://github.com/qutebrowser/qutebrowser/pull/962#discussion_r40256987
        # and https://github.com/qutebrowser/qutebrowser/issues/1053
        request = interceptors.Request(first_party_url=None, request_url=url)
        interceptors.run(request)
        if request.is_blocked:
            log.downloads.debug("Skipping {}, host-blocked".format(url))
            # We still need an empty file in the output, QWebView can be pretty
            # picky about displaying a file correctly when not all assets are
            # at least referenced in the mhtml file.
            self.writer.add_file(urlutils.encoded_url(url), b'')
            return

        download_manager = objreg.get('qtnetwork-download-manager')
        target = downloads.FileObjDownloadTarget(_NoCloseBytesIO())
        item = download_manager.get(url, target=target,
                                    auto_remove=True)
        self.pending_downloads.add((url, item))
        item.finished.connect(functools.partial(self._finished, url, item))
        item.error.connect(functools.partial(self._error, url, item))
        item.cancelled.connect(functools.partial(self._cancelled, url, item))

    def _finished(self, url, item):
        """Callback when a single asset is downloaded.

        Args:
            url: The original url of the asset as QUrl.
            item: The DownloadItem given by the DownloadManager
        """
        assert self.writer is not None

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

        if mime.lower() == 'text/css' or url.fileName().endswith('.css'):
            # We can't always assume that CSS files are UTF-8, but CSS files
            # shouldn't contain many non-ASCII characters anyway (in most
            # cases). Using "ignore" lets us decode the file even if it's
            # invalid UTF-8 data.
            # The file written to the MHTML file won't be modified by this
            # decoding, since there we're taking the original bytestream.
            try:
                css_string = item.fileobj.getvalue().decode('utf-8')
            except UnicodeDecodeError:
                log.downloads.warning("Invalid UTF-8 data in {}".format(url))
                css_string = item.fileobj.getvalue().decode('utf-8', 'ignore')
            import_urls = _get_css_imports(css_string)
            for import_url in import_urls:
                absolute_url = url.resolved(QUrl(import_url))
                self._fetch_url(absolute_url)

        encode = E_QUOPRI if mime.startswith('text/') else E_BASE64
        # Our MHTML handler refuses non-ASCII headers. This will replace every
        # non-ASCII char with '?'. This is probably okay, as official Content-
        # Type headers contain ASCII only anyway. Anything else is madness.
        mime = utils.force_encoding(mime, 'ascii')
        self.writer.add_file(urlutils.encoded_url(url),
                             item.fileobj.getvalue(), mime, encode)
        item.fileobj.actual_close()
        if self.pending_downloads:
            return
        self._finish_file()

    def _error(self, url, item, *_args):
        """Callback when a download error occurred.

        Args:
            url: The original url of the asset as QUrl.
            item: The DownloadItem given by the DownloadManager.
        """
        assert self.writer is not None
        try:
            self.pending_downloads.remove((url, item))
        except KeyError:
            # This might happen if .collect_zombies() calls .finished() and the
            # error handler will be called after .collect_zombies
            log.downloads.debug("Oops! Download already gone: {}".format(item))
            return
        item.fileobj.actual_close()
        # Add a stub file, see comment in .fetch_url() for more information
        self.writer.add_file(urlutils.encoded_url(url), b'')
        if self.pending_downloads:
            return
        self._finish_file()

    def _cancelled(self, url, item):
        """Callback when a download is cancelled by the user.

        Args:
            url: The original url of the asset as QUrl.
            item: The DownloadItem given by the DownloadManager.
        """
        # This callback is called before _finished, so there's no need to
        # remove the item or close the fileobject.
        log.downloads.debug("MHTML download cancelled by user: {}".format(url))
        # Write an empty file instead
        item.fileobj.seek(0)
        item.fileobj.truncate()

    def _finish_file(self):
        """Save the file to the filename given in __init__."""
        assert self.writer is not None

        if self._finished_file:
            log.downloads.debug("finish_file called twice, ignored!")
            return
        self._finished_file = True
        log.downloads.debug("All assets downloaded, ready to finish off!")

        if isinstance(self.target, downloads.FileDownloadTarget):
            fobj = open(self.target.filename, 'wb')
        elif isinstance(self.target, downloads.FileObjDownloadTarget):
            fobj = self.target.fileobj
        elif isinstance(self.target, downloads.OpenFileDownloadTarget):
            try:
                fobj = downloads.temp_download_manager.get_tmpfile(
                    self.tab.title() + '.mhtml')
            except OSError as exc:
                msg = "Download error: {}".format(exc)
                message.error(msg)
                return
        else:
            raise ValueError("Invalid DownloadTarget given: {!r}"
                             .format(self.target))

        try:
            with fobj:
                self.writer.write_to(fobj)
        except OSError as error:
            message.error("Could not save file: {}".format(error))
            return
        log.downloads.debug("File successfully written.")
        message.info("Page saved as {}".format(self.target))

        if isinstance(self.target, downloads.OpenFileDownloadTarget):
            utils.open_file(fobj.name, self.target.cmdline)

    def _collect_zombies(self):
        """Collect done downloads and add their data to the MHTML file.

        This is needed if a download finishes before attaching its
        finished signal.
        """
        items = {(url, item) for url, item in self.pending_downloads
                 if item.done}
        log.downloads.debug("Zombie downloads: {}".format(items))
        for url, item in items:
            self._finished(url, item)


class _NoCloseBytesIO(io.BytesIO):

    """BytesIO that can't be .closed().

    This is needed to prevent the DownloadManager from closing the stream, thus
    discarding the data.
    """

    def close(self):
        """Do nothing."""

    def actual_close(self):
        """Close the stream."""
        super().close()


def _start_download(target, tab):
    """Start downloading the current page and all assets to an MHTML file.

    This will overwrite dest if it already exists.

    Args:
        target: The DownloadTarget where the resulting file should be saved.
        tab: Specify the tab whose page should be loaded.
    """
    loader = _Downloader(tab, target)
    loader.run()


def start_download_checked(target, tab):
    """First check if dest is already a file, then start the download.

    Args:
        target: The DownloadTarget where the resulting file should be saved.
        tab: Specify the tab whose page should be loaded.
    """
    if not isinstance(target, downloads.FileDownloadTarget):
        _start_download(target, tab)
        return
    # The default name is 'page title.mhtml'
    title = tab.title()
    default_name = utils.sanitize_filename(title + '.mhtml', shorten=True)

    # Remove characters which cannot be expressed in the file system encoding
    encoding = sys.getfilesystemencoding()
    default_name = utils.force_encoding(default_name, encoding)
    dest = utils.force_encoding(target.filename, encoding)

    dest = os.path.expanduser(dest)

    # See if we already have an absolute path
    path = downloads.create_full_filename(default_name, dest)
    if path is None:
        # We still only have a relative path, prepend download_dir and
        # try again.
        path = downloads.create_full_filename(
            default_name, os.path.join(downloads.download_dir(), dest))
    downloads.last_used_directory = os.path.dirname(path)

    # Avoid downloading files if we can't save the output anyway...
    # Yes, this is prone to race conditions, but we're checking again before
    # saving the file anyway.
    if not os.path.isdir(os.path.dirname(path)):
        folder = os.path.dirname(path)
        message.error("Directory {} does not exist.".format(folder))
        return

    target = downloads.FileDownloadTarget(path)
    if not os.path.isfile(path):
        _start_download(target, tab=tab)
        return

    q = usertypes.Question()
    q.mode = usertypes.PromptMode.yesno
    q.title = "Overwrite existing file?"
    q.text = "<b>{}</b> already exists. Overwrite?".format(
        html.escape(path))
    q.completed.connect(q.deleteLater)
    q.answered_yes.connect(functools.partial(
        _start_download, target, tab=tab))
    message.global_bridge.ask(q, blocking=False)
