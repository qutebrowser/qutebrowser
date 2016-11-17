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

"""Download manager."""

import io
import shutil
import functools
import collections

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QTimer
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply

from qutebrowser.utils import message, usertypes, log, urlutils
from qutebrowser.browser import downloads
from qutebrowser.browser.webkit import http
from qutebrowser.browser.webkit.network import networkmanager


_RetryInfo = collections.namedtuple('_RetryInfo', ['request', 'manager'])


class DownloadItem(downloads.AbstractDownloadItem):

    """A single download currently running.

    There are multiple ways the data can flow from the QNetworkReply to the
    disk.

    If the filename/file object is known immediately when starting the
    download, QNetworkReply's readyRead writes to the target file directly.

    If not, readyRead is ignored and with self._read_timer we periodically read
    into the self._buffer BytesIO slowly, so some broken servers don't close
    our connection.

    As soon as we know the file object, we copy self._buffer over and the next
    readyRead will write to the real file object.

    Class attributes:
        _MAX_REDIRECTS: The maximum redirection count.

    Attributes:
        _retry_info: A _RetryInfo instance.
        _redirects: How many time we were redirected already.
        _buffer: A BytesIO object to buffer incoming data until we know the
                 target file.
        _read_timer: A Timer which reads the QNetworkReply into self._buffer
                     periodically.
        _manager: The DownloadManager which started this download
        _reply: The QNetworkReply associated with this download.
        _autoclose: Whether to close the associated file when the download is
                    done.

    Signals:
        adopt_download: Emitted when a download is retried and should be
                        adopted by the QNAM if needed.
                        arg 0: The new DownloadItem
    """

    _MAX_REDIRECTS = 10
    adopt_download = pyqtSignal(object)  # DownloadItem

    def __init__(self, reply, manager):
        """Constructor.

        Args:
            reply: The QNetworkReply to download.
        """
        super().__init__(parent=manager)
        self.fileobj = None
        self.raw_headers = {}

        self._autoclose = True
        self._manager = manager
        self._retry_info = None
        self._reply = None
        self._buffer = io.BytesIO()
        self._read_timer = usertypes.Timer(self, name='download-read-timer')
        self._read_timer.setInterval(500)
        self._read_timer.timeout.connect(self._on_read_timer_timeout)
        self._redirects = 0
        self._init_reply(reply)

    def _create_fileobj(self):
        """Create a file object using the internal filename."""
        try:
            fileobj = open(self._filename, 'wb')
        except OSError as e:
            self._die(e.strerror)
        else:
            self._set_fileobj(fileobj)

    def _do_die(self):
        """Abort the download and emit an error."""
        self._read_timer.stop()
        self._reply.downloadProgress.disconnect()
        self._reply.finished.disconnect()
        self._reply.error.disconnect()
        self._reply.readyRead.disconnect()
        with log.hide_qt_warning('QNetworkReplyImplPrivate::error: Internal '
                                 'problem, this method must only be called '
                                 'once.'):
            # See https://codereview.qt-project.org/#/c/107863/
            self._reply.abort()
        self._reply.deleteLater()
        self._reply = None
        if self.fileobj is not None:
            try:
                self.fileobj.close()
            except OSError:
                log.downloads.exception("Error while closing file object")

    def _init_reply(self, reply):
        """Set a new reply and connect its signals.

        Args:
            reply: The QNetworkReply to handle.
        """
        self.done = False
        self.successful = False
        self._reply = reply
        reply.setReadBufferSize(16 * 1024 * 1024)  # 16 MB
        reply.downloadProgress.connect(self.stats.on_download_progress)
        reply.finished.connect(self._on_reply_finished)
        reply.error.connect(self._on_reply_error)
        reply.readyRead.connect(self._on_ready_read)
        reply.metaDataChanged.connect(self._on_meta_data_changed)
        self._retry_info = _RetryInfo(request=reply.request(),
                                      manager=reply.manager())
        if not self.fileobj:
            self._read_timer.start()
        # We could have got signals before we connected slots to them.
        # Here no signals are connected to the DownloadItem yet, so we use a
        # singleShot QTimer to emit them after they are connected.
        if reply.error() != QNetworkReply.NoError:
            QTimer.singleShot(0, lambda: self._die(reply.errorString()))

    def _do_cancel(self):
        if self._reply is not None:
            self._reply.finished.disconnect(self._on_reply_finished)
            self._reply.abort()
            self._reply.deleteLater()
            self._reply = None
        if self.fileobj is not None:
            self.fileobj.close()
        self.cancelled.emit()

    @pyqtSlot()
    def retry(self):
        """Retry a failed download."""
        assert self.done
        assert not self.successful
        new_reply = self._retry_info.manager.get(self._retry_info.request)
        new_download = self._manager.fetch(new_reply,
                                           suggested_filename=self.basename)
        self.adopt_download.emit(new_download)
        self.cancel()

    def _get_open_filename(self):
        filename = self._filename
        if filename is None:
            filename = getattr(self.fileobj, 'name', None)
        return filename

    def _ensure_can_set_filename(self, filename):
        if self.fileobj is not None:  # pragma: no cover
            raise ValueError("fileobj was already set! filename: {}, "
                             "existing: {}, fileobj {}".format(
                                 filename, self._filename, self.fileobj))

    def _after_set_filename(self):
        self._create_fileobj()

    def _ask_confirm_question(self, title, msg):
        no_action = functools.partial(self.cancel, remove_data=False)
        message.confirm_async(title=title, text=msg,
                              yes_action=self._after_set_filename,
                              no_action=no_action, cancel_action=no_action,
                              abort_on=[self.cancelled, self.error])

    def _set_fileobj(self, fileobj, *, autoclose=True):
        """"Set the file object to write the download to.

        Args:
            fileobj: A file-like object.
        """
        if self.fileobj is not None:  # pragma: no cover
            raise ValueError("fileobj was already set! Old: {}, new: "
                             "{}".format(self.fileobj, fileobj))
        self.fileobj = fileobj
        self._autoclose = autoclose
        try:
            self._read_timer.stop()
            log.downloads.debug("buffer: {} bytes".format(self._buffer.tell()))
            self._buffer.seek(0)
            shutil.copyfileobj(self._buffer, fileobj)
            self._buffer.close()
            if self._reply.isFinished():
                # Downloading to the buffer in RAM has already finished so we
                # write out the data and clean up now.
                self._on_reply_finished()
            else:
                # Since the buffer already might be full, on_ready_read might
                # not be called at all anymore, so we force it here to flush
                # the buffer and continue receiving new data.
                self._on_ready_read()
        except OSError as e:
            self._die(e.strerror)

    def _set_tempfile(self, fileobj):
        self._set_fileobj(fileobj)

    def _finish_download(self):
        """Write buffered data to disk and finish the QNetworkReply."""
        log.downloads.debug("Finishing download...")
        if self._reply.isOpen():
            self.fileobj.write(self._reply.readAll())
        if self._autoclose:
            self.fileobj.close()
        self.successful = self._reply.error() == QNetworkReply.NoError
        self._reply.close()
        self._reply.deleteLater()
        self._reply = None
        self.finished.emit()
        self.done = True
        log.downloads.debug("Download {} finished".format(self.basename))
        self.data_changed.emit()

    @pyqtSlot()
    def _on_reply_finished(self):
        """Clean up when the download was finished.

        Note when this gets called, only the QNetworkReply has finished. This
        doesn't mean the download (i.e. writing data to the disk) is finished
        as well. Therefore, we can't close() the QNetworkReply in here yet.
        """
        if self._reply is None:
            return
        self._read_timer.stop()
        self.stats.finish()
        is_redirected = self._handle_redirect()
        if is_redirected:
            return
        log.downloads.debug("Reply finished, fileobj {}".format(self.fileobj))
        if self.fileobj is not None:
            # We can do a "delayed" write immediately to empty the buffer and
            # clean up.
            self._finish_download()

    @pyqtSlot()
    def _on_ready_read(self):
        """Read available data and save file when ready to read."""
        if self.fileobj is None or self._reply is None:
            # No filename has been set yet (so we don't empty the buffer) or we
            # got a readyRead after the reply was finished (which happens on
            # qute:log for example).
            return
        if not self._reply.isOpen():
            raise OSError("Reply is closed!")
        try:
            self.fileobj.write(self._reply.readAll())
        except OSError as e:
            self._die(e.strerror)

    @pyqtSlot('QNetworkReply::NetworkError')
    def _on_reply_error(self, code):
        """Handle QNetworkReply errors."""
        if code == QNetworkReply.OperationCanceledError:
            return
        else:
            self._die(self._reply.errorString())

    @pyqtSlot()
    def _on_read_timer_timeout(self):
        """Read some bytes from the QNetworkReply periodically."""
        if not self._reply.isOpen():
            raise OSError("Reply is closed!")
        data = self._reply.read(1024)
        if data is not None:
            self._buffer.write(data)

    @pyqtSlot()
    def _on_meta_data_changed(self):
        """Update the download's metadata."""
        if self._reply is None:
            return
        self.raw_headers = {}
        for key, value in self._reply.rawHeaderPairs():
            self.raw_headers[bytes(key)] = bytes(value)

    def _handle_redirect(self):
        """Handle an HTTP redirect.

        Return:
            True if the download was redirected, False otherwise.
        """
        redirect = self._reply.attribute(
            QNetworkRequest.RedirectionTargetAttribute)
        if redirect is None or redirect.isEmpty():
            return False
        new_url = self._reply.url().resolved(redirect)
        new_request = self._reply.request()
        if new_url == new_request.url():
            return False

        if self._redirects > self._MAX_REDIRECTS:
            self._die("Maximum redirection count reached!")
            self.delete()
            return True  # so on_reply_finished aborts

        log.downloads.debug("{}: Handling redirect".format(self))
        self._redirects += 1
        new_request.setUrl(new_url)
        old_reply = self._reply
        old_reply.finished.disconnect(self._on_reply_finished)
        self._read_timer.stop()
        self._reply = None
        if self.fileobj is not None:
            self.fileobj.seek(0)

        log.downloads.debug("redirected: {} -> {}".format(
            old_reply.url(), new_request.url()))
        new_reply = old_reply.manager().get(new_request)
        self._init_reply(new_reply)

        old_reply.deleteLater()
        return True

    def _uses_nam(self, nam):
        """Check if this download uses the given QNetworkAccessManager."""
        running_nam = self._reply is not None and self._reply.manager() is nam
        # user could request retry after tab is closed.
        retry_nam = (self.done and (not self.successful) and
                     self._retry_info.manager is nam)
        return running_nam or retry_nam


class DownloadManager(downloads.AbstractDownloadManager):

    """Manager for currently running downloads.

    Attributes:
        _networkmanager: A NetworkManager for generic downloads.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._networkmanager = networkmanager.NetworkManager(
            win_id, None, self)

    @pyqtSlot('QUrl')
    def get(self, url, **kwargs):
        """Start a download with a link URL.

        Args:
            url: The URL to get, as QUrl
            **kwargs: passed to get_request().

        Return:
            The created DownloadItem.
        """
        if not url.isValid():
            urlutils.invalid_url_error(url, "start download")
            return
        req = QNetworkRequest(url)
        return self.get_request(req, **kwargs)

    def get_request(self, request, *, target=None, **kwargs):
        """Start a download with a QNetworkRequest.

        Args:
            request: The QNetworkRequest to download.
            target: Where to save the download as downloads.DownloadTarget.
            **kwargs: Passed to _fetch_request.

        Return:
            The created DownloadItem.
        """
        # WORKAROUND for Qt corrupting data loaded from cache:
        # https://bugreports.qt.io/browse/QTBUG-42757
        request.setAttribute(QNetworkRequest.CacheLoadControlAttribute,
                             QNetworkRequest.AlwaysNetwork)

        if request.url().scheme().lower() != 'data':
            suggested_fn = urlutils.filename_from_url(request.url())
        else:
            # We might be downloading a binary blob embedded on a page or even
            # generated dynamically via javascript. We try to figure out a more
            # sensible name than the base64 content of the data.
            origin = request.originatingObject()
            try:
                origin_url = origin.url()
            except AttributeError:
                # Raised either if origin is None or some object that doesn't
                # have its own url. We're probably fine with a default fallback
                # then.
                suggested_fn = 'binary blob'
            else:
                # Use the originating URL as a base for the filename (works
                # e.g. for pdf.js).
                suggested_fn = urlutils.filename_from_url(origin_url)

        if suggested_fn is None:
            suggested_fn = 'qutebrowser-download'

        return self._fetch_request(request,
                                   target=target,
                                   suggested_filename=suggested_fn,
                                   **kwargs)

    def _fetch_request(self, request, *, qnam=None, **kwargs):
        """Download a QNetworkRequest to disk.

        Args:
            request: The QNetworkRequest to download.
            qnam: The QNetworkAccessManager to use.
            **kwargs: passed to fetch().

        Return:
            The created DownloadItem.
        """
        if qnam is None:
            qnam = self._networkmanager
        reply = qnam.get(request)
        return self.fetch(reply, **kwargs)

    @pyqtSlot('QNetworkReply')
    def fetch(self, reply, *, target=None, auto_remove=False,
              suggested_filename=None, prompt_download_directory=None):
        """Download a QNetworkReply to disk.

        Args:
            reply: The QNetworkReply to download.
            target: Where to save the download as downloads.DownloadTarget.
            auto_remove: Whether to remove the download even if
                         ui -> remove-finished-downloads is set to -1.

        Return:
            The created DownloadItem.
        """
        if not suggested_filename:
            try:
                suggested_filename = target.suggested_filename()
            except downloads.NoFilenameError:
                _, suggested_filename = http.parse_content_disposition(reply)
        log.downloads.debug("fetch: {} -> {}".format(reply.url(),
                                                     suggested_filename))
        download = DownloadItem(reply, manager=self)
        self._init_item(download, auto_remove, suggested_filename)

        if target is not None:
            download.set_target(target)
            return download

        # Neither filename nor fileobj were given

        filename = downloads.immediate_download_path(prompt_download_directory)
        if filename is not None:
            # User doesn't want to be asked, so just use the download_dir
            target = downloads.FileDownloadTarget(filename)
            download.set_target(target)
            return download

        # Ask the user for a filename
        question = downloads.get_filename_question(
            suggested_filename=suggested_filename, url=reply.url(),
            parent=self)
        self._init_filename_question(question, download)
        message.global_bridge.ask(question, blocking=False)

        return download

    def has_downloads_with_nam(self, nam):
        """Check if the DownloadManager has any downloads with the given QNAM.

        Args:
            nam: The QNetworkAccessManager to check.

        Return:
            A boolean.
        """
        assert nam.adopted_downloads == 0
        for download in self.downloads:
            if download._uses_nam(nam):  # pylint: disable=protected-access
                nam.adopt_download(download)
        return nam.adopted_downloads
