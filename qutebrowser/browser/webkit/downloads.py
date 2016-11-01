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
import os
import sys
import os.path
import shutil
import functools
import tempfile
import collections
import html

import sip
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, QObject, QTimer,
                          Qt, QAbstractListModel, QModelIndex, QUrl)
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply

from qutebrowser.config import config
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import (message, usertypes, log, utils, urlutils,
                               objreg, standarddir, qtutils)
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
        done: Whether the download is finished.
        stats: A DownloadItemStats object.
        index: The index of the download in the view.
        successful: Whether the download has completed successfully.
        error_msg: The current error message, or None
        autoclose: Whether to close the associated file if the download is
                   done.
        fileobj: The file object to download the file to.
        _retry_info: A _RetryInfo instance.
        raw_headers: The headers sent by the server.
        _filename: The filename of the download.
        _redirects: How many time we were redirected already.
        _buffer: A BytesIO object to buffer incoming data until we know the
                 target file.
        _read_timer: A Timer which reads the QNetworkReply into self._buffer
                     periodically.
        _win_id: The window ID the DownloadItem runs in.
        _dead: Whether the Download has _die()'d.
        _reply: The QNetworkReply associated with this download.

    Signals:
        data_changed: The downloads metadata changed.
        finished: The download was finished.
        cancelled: The download was cancelled.
        error: An error with the download occurred.
               arg: The error message as string.
        adopt_download: Emitted when a download is retried and should be adopted
                        by the QNAM if needed..
                        arg 0: The new DownloadItem
        remove_requested: Emitted when the removal of this download was
                          requested.
    """

    _MAX_REDIRECTS = 10
    adopt_download = pyqtSignal(object)  # DownloadItem

    def __init__(self, reply, win_id, parent=None):
        """Constructor.

        Args:
            reply: The QNetworkReply to download.
        """
        super().__init__(parent)
        self.autoclose = True
        self.fileobj = None
        self.raw_headers = {}

        self._filename = None
        self._dead = False

        self._retry_info = None
        self._reply = None
        self._buffer = io.BytesIO()
        self._read_timer = usertypes.Timer(self, name='download-read-timer')
        self._read_timer.setInterval(500)
        self._read_timer.timeout.connect(self._on_read_timer_timeout)
        self._redirects = 0
        self._init_reply(reply)
        self._win_id = win_id

    def _create_fileobj(self):
        """Create a file object using the internal filename."""
        try:
            fileobj = open(self._filename, 'wb')
        except OSError as e:
            self._die(e.strerror)
        else:
            self._set_fileobj(fileobj)

    def _ask_confirm_question(self, title, msg):
        """Create a Question object to be asked."""
        # FIXME:qtwebengine move this?
        no_action = functools.partial(self.cancel, remove_data=False)
        message.confirm_async(title=title, text=msg,
                              yes_action=self._after_set_filename,
                              no_action=no_action, cancel_action=no_action,
                              abort_on=[self.cancelled, self.error])

    def _die(self, msg):
        """Abort the download and emit an error."""
        super()._die(msg)
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

    @pyqtSlot()
    def retry(self):
        """Retry a failed download."""
        assert self.done
        assert not self.successful
        download_manager = objreg.get('download-manager', scope='window',
                                      window=self._win_id)
        new_reply = self._retry_info.manager.get(self._retry_info.request)
        new_download = download_manager.fetch(
            new_reply, suggested_filename=self.basename)
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

    def _set_fileobj(self, fileobj):
        """"Set the file object to write the download to.

        Args:
            fileobj: A file-like object.
        """
        if self.fileobj is not None:  # pragma: no cover
            raise ValueError("fileobj was already set! Old: {}, new: "
                             "{}".format(self.fileobj, fileobj))
        self.fileobj = fileobj
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

    def _finish_download(self):
        """Write buffered data to disk and finish the QNetworkReply."""
        log.downloads.debug("Finishing download...")
        if self._reply.isOpen():
            self.fileobj.write(self._reply.readAll())
        if self.autoclose:
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

    def uses_nam(self, nam):
        """Check if this download uses the given QNetworkAccessManager."""
        running_nam = self._reply is not None and self._reply.manager() is nam
        # user could request retry after tab is closed.
        retry_nam = (self.done and (not self.successful) and
                     self._retry_info.manager is nam)
        return running_nam or retry_nam

    def _open_if_successful(self, cmdline):
        """Open the downloaded file, but only if it was successful.

        Args:
            cmdline: Passed to DownloadItem.open_file().
        """
        if not self.successful:
            log.downloads.debug("{} finished but not successful, not opening!"
                                .format(self))
            return
        self.open_file(cmdline)

    def set_target(self, target):
        """Set the target for a given download.

        Args:
            target: The usertypes.DownloadTarget for this download.
        """
        if isinstance(target, usertypes.FileObjDownloadTarget):
            self._set_fileobj(target.fileobj)
            self.autoclose = False
        elif isinstance(target, usertypes.FileDownloadTarget):
            self.set_filename(target.filename)
        elif isinstance(target, usertypes.OpenFileDownloadTarget):
            tmp_manager = objreg.get('temporary-downloads')
            try:
                fobj = tmp_manager.get_tmpfile(self.basename)
            except OSError as exc:
                msg = "Download error: {}".format(exc)
                message.error(msg)
                self.cancel()
                return
            self.finished.connect(
                functools.partial(self._open_if_successful, target.cmdline))
            self.autoclose = True
            self._set_fileobj(fobj)
        else:  # pragma: no cover
            raise ValueError("Unknown download target: {}".format(target))


class DownloadManager(QObject):

    """Manager for currently running downloads.

    Attributes:
        downloads: A list of active DownloadItems.
        questions: A list of Question objects to not GC them.
        _networkmanager: A NetworkManager for generic downloads.
        _win_id: The window ID the DownloadManager runs in.

    Signals:
        begin_remove_rows: Emitted before downloads are removed.
        end_remove_rows: Emitted after downloads are removed.
        begin_insert_rows: Emitted before downloads are inserted.
        end_insert_rows: Emitted after downloads are inserted.
        data_changed: Emitted when the data of the model changed.
                      The arguments are int indices to the downloads.
    """

    # parent, first, last
    begin_remove_rows = pyqtSignal(QModelIndex, int, int)
    end_remove_rows = pyqtSignal()
    # parent, first, last
    begin_insert_rows = pyqtSignal(QModelIndex, int, int)
    end_insert_rows = pyqtSignal()
    data_changed = pyqtSignal(int, int)  # begin, end

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self.downloads = []
        self.questions = []
        self._networkmanager = networkmanager.NetworkManager(
            win_id, None, self)
        self._update_timer = usertypes.Timer(self, 'download-update')
        self._update_timer.timeout.connect(self._update_gui)
        self._update_timer.setInterval(_REFRESH_INTERVAL)

    def __repr__(self):
        return utils.get_repr(self, downloads=len(self.downloads))

    def _postprocess_question(self, q):
        """Postprocess a Question object that is asked."""
        q.destroyed.connect(functools.partial(self.questions.remove, q))
        # We set the mode here so that other code that uses ask_for_filename
        # doesn't need to handle the special download mode.
        q.mode = usertypes.PromptMode.download
        self.questions.append(q)

    @pyqtSlot()
    def _update_gui(self):
        """Periodical GUI update of all items."""
        assert self.downloads
        for dl in self.downloads:
            dl.stats.update_speed()
        self.data_changed.emit(0, -1)

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
            target: Where to save the download as usertypes.DownloadTarget.
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
            target: Where to save the download as usertypes.DownloadTarget.
            auto_remove: Whether to remove the download even if
                         ui -> remove-finished-downloads is set to -1.

        Return:
            The created DownloadItem.
        """
        if not suggested_filename:
            if isinstance(target, usertypes.FileDownloadTarget):
                suggested_filename = os.path.basename(target.filename)
            elif (isinstance(target, usertypes.FileObjDownloadTarget) and
                  getattr(target.fileobj, 'name', None)):
                suggested_filename = target.fileobj.name
            else:
                _, suggested_filename = http.parse_content_disposition(reply)
        log.downloads.debug("fetch: {} -> {}".format(reply.url(),
                                                     suggested_filename))
        download = DownloadItem(reply, self._win_id, self)
        download.cancelled.connect(download.remove)
        download.remove_requested.connect(functools.partial(
            self._remove_item, download))

        delay = config.get('ui', 'remove-finished-downloads')
        if delay > -1:
            download.finished.connect(
                lambda: QTimer.singleShot(delay, download.remove))
        elif auto_remove:
            download.finished.connect(download.remove)

        download.data_changed.connect(
            functools.partial(self._on_data_changed, download))
        download.error.connect(self._on_error)
        download.basename = suggested_filename
        idx = len(self.downloads)
        download.index = idx + 1  # "Human readable" index
        self.begin_insert_rows.emit(QModelIndex(), idx, idx)
        self.downloads.append(download)
        self.end_insert_rows.emit()

        if not self._update_timer.isActive():
            self._update_timer.start()

        if target is not None:
            download.set_target(target)
            return download

        # Neither filename nor fileobj were given, prepare a question
        filename, q = ask_for_filename(
            suggested_filename, parent=self,
            prompt_download_directory=prompt_download_directory,
            url=reply.url())

        # User doesn't want to be asked, so just use the download_dir
        if filename is not None:
            target = usertypes.FileDownloadTarget(filename)
            download.set_target(target)
            return download

        # Ask the user for a filename
        self._postprocess_question(q)
        q.answered.connect(download.set_target)
        q.cancelled.connect(download.cancel)
        download.cancelled.connect(q.abort)
        download.error.connect(q.abort)
        q.ask()

        return download

    @pyqtSlot(DownloadItem)
    def _on_data_changed(self, download):
        """Emit data_changed signal when download data changed."""
        try:
            idx = self.downloads.index(download)
        except ValueError:
            # download has been deleted in the meantime
            return
        self.data_changed.emit(idx, idx)

    @pyqtSlot(str)
    def _on_error(self, msg):
        """Display error message on download errors."""
        message.error("Download error: {}".format(msg))

    def has_downloads_with_nam(self, nam):
        """Check if the DownloadManager has any downloads with the given QNAM.

        Args:
            nam: The QNetworkAccessManager to check.

        Return:
            A boolean.
        """
        assert nam.adopted_downloads == 0
        for download in self.downloads:
            if download.uses_nam(nam):
                nam.adopt_download(download)
        return nam.adopted_downloads

    @pyqtSlot(DownloadItem)
    def _remove_item(self, download):
        """Remove a given download."""
        if sip.isdeleted(self):
            # https://github.com/The-Compiler/qutebrowser/issues/1242
            return
        try:
            idx = self.downloads.index(download)
        except ValueError:
            # already removed
            return
        self.begin_remove_rows.emit(QModelIndex(), idx, idx)
        del self.downloads[idx]
        self.end_remove_rows.emit()
        download.deleteLater()
        self._update_indexes()
        if not self.downloads:
            self._update_timer.stop()
        log.downloads.debug("Removed download {}".format(download))

    def _update_indexes(self):
        """Update indexes of all DownloadItems."""
        first_idx = None
        for i, d in enumerate(self.downloads, 1):
            if first_idx is None and d.index != i:
                first_idx = i - 1
            d.index = i
        if first_idx is not None:
            self.data_changed.emit(first_idx, -1)


class DownloadModel(QAbstractListModel):

    """A list model showing downloads."""

    def __init__(self, downloader, parent=None):
        super().__init__(parent)
        self._downloader = downloader
        # FIXME we'll need to translate indices here...
        downloader.data_changed.connect(self._on_data_changed)
        downloader.begin_insert_rows.connect(self.beginInsertRows)
        downloader.end_insert_rows.connect(self.endInsertRows)
        downloader.begin_remove_rows.connect(self.beginRemoveRows)
        downloader.end_remove_rows.connect(self.endRemoveRows)

    def _all_downloads(self):
        """Combine downloads from both downloaders."""
        return self._downloader.downloads[:]

    def __len__(self):
        return len(self._all_downloads())

    def __iter__(self):
        return iter(self._all_downloads())

    def __getitem__(self, idx):
        return self._all_downloads()[idx]

    @pyqtSlot(int, int)
    def _on_data_changed(self, start, end):
        """Called when a downloader's data changed.

        Args:
            start: The first changed index as int.
            end: The last changed index as int, or -1 for all indices.
        """
        # FIXME we'll need to translate indices here...
        start_index = self.index(start, 0)
        qtutils.ensure_valid(start_index)
        if end == -1:
            end_index = self.last_index()
        else:
            end_index = self.index(end, 0)
            qtutils.ensure_valid(end_index)
        self.dataChanged.emit(start_index, end_index)

    def _raise_no_download(self, count):
        """Raise an exception that the download doesn't exist.

        Args:
            count: The index of the download
        """
        if not count:
            raise cmdexc.CommandError("There's no download!")
        raise cmdexc.CommandError("There's no download {}!".format(count))

    @cmdutils.register(instance='download-model', scope='window')
    @cmdutils.argument('count', count=True)
    def download_cancel(self, all_=False, count=0):
        """Cancel the last/[count]th download.

        Args:
            all_: Cancel all running downloads
            count: The index of the download to cancel.
        """
        downloads = self._all_downloads()
        if all_:
            for download in downloads:
                if not download.done:
                    download.cancel()
        else:
            try:
                download = downloads[count - 1]
            except IndexError:
                self._raise_no_download(count)
            if download.done:
                if not count:
                    count = len(self)
                raise cmdexc.CommandError("Download {} is already done!"
                                        .format(count))
            download.cancel()

    @cmdutils.register(instance='download-model', scope='window')
    @cmdutils.argument('count', count=True)
    def download_delete(self, count=0):
        """Delete the last/[count]th download from disk.

        Args:
            count: The index of the download to delete.
        """
        try:
            download = self[count - 1]
        except IndexError:
            self._raise_no_download(count)
        if not download.successful:
            if not count:
                count = len(self)
            raise cmdexc.CommandError("Download {} is not done!".format(count))
        download.delete()
        download.remove()
        log.downloads.debug("deleted download {}".format(download))

    @cmdutils.register(instance='download-model', scope='window', maxsplit=0)
    @cmdutils.argument('count', count=True)
    def download_open(self, cmdline: str=None, count=0):
        """Open the last/[count]th download.

        If no specific command is given, this will use the system's default
        application to open the file.

        Args:
            cmdline: The command which should be used to open the file. A `{}`
                     is expanded to the temporary file name. If no `{}` is
                     present, the filename is automatically appended to the
                     cmdline.
            count: The index of the download to open.
        """
        try:
            download = self[count - 1]
        except IndexError:
            self._raise_no_download(count)
        if not download.successful:
            if not count:
                count = len(self)
            raise cmdexc.CommandError("Download {} is not done!".format(count))
        download.open_file(cmdline)

    @cmdutils.register(instance='download-model', scope='window')
    @cmdutils.argument('count', count=True)
    def download_retry(self, count=0):
        """Retry the first failed/[count]th download.

        Args:
            count: The index of the download to retry.
        """
        if count:
            try:
                download = self[count - 1]
            except IndexError:
                self._raise_no_download(count)
            if download.successful or not download.done:
                raise cmdexc.CommandError("Download {} did not fail!".format(
                    count))
        else:
            to_retry = [d for d in self if d.done and not d.successful]
            if not to_retry:
                raise cmdexc.CommandError("No failed downloads!")
            else:
                download = to_retry[0]
        download.retry()

    def can_clear(self):
        """Check if there are finished downloads to clear."""
        return any(download.done for download in self)

    @cmdutils.register(instance='download-model', scope='window')
    def download_clear(self):
        """Remove all finished downloads from the list."""
        for download in self:
            if download.done:
                download.remove()

    @cmdutils.register(instance='download-model', scope='window')
    @cmdutils.argument('count', count=True)
    def download_remove(self, all_=False, count=0):
        """Remove the last/[count]th download from the list.

        Args:
            all_: Remove all finished downloads.
            count: The index of the download to remove.
        """
        if all_:
            self.download_clear()
        else:
            try:
                download = self[count - 1]
            except IndexError:
                self._raise_no_download(count)
            if not download.done:
                if not count:
                    count = len(self)
                raise cmdexc.CommandError("Download {} is not done!"
                                          .format(count))
            download.remove()

    def running_downloads(self):
        """Return the amount of still running downloads.

        Return:
            The number of unfinished downloads.
        """
        return sum(1 for download in self if not download.done)

    def last_index(self):
        """Get the last index in the model.

        Return:
            A (possibly invalid) QModelIndex.
        """
        idx = self.index(self.rowCount() - 1)
        return idx

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Simple constant header."""
        if (section == 0 and orientation == Qt.Horizontal and
                role == Qt.DisplayRole):
            return "Downloads"
        else:
            return ""

    def data(self, index, role):
        """Download data from DownloadManager."""
        if not index.isValid():
            return None

        if index.parent().isValid() or index.column() != 0:
            return None

        item = self[index.row()]
        if role == Qt.DisplayRole:
            data = str(item)
        elif role == Qt.ForegroundRole:
            data = item.get_status_color('fg')
        elif role == Qt.BackgroundRole:
            data = item.get_status_color('bg')
        elif role == ModelRole.item:
            data = item
        elif role == Qt.ToolTipRole:
            if item.error_msg is None:
                data = None
            else:
                return item.error_msg
        else:
            data = None
        return data

    def flags(self, index):
        """Override flags so items aren't selectable.

        The default would be Qt.ItemIsEnabled | Qt.ItemIsSelectable.
        """
        if not index.isValid():
            return Qt.ItemFlags()
        return Qt.ItemIsEnabled | Qt.ItemNeverHasChildren

    def rowCount(self, parent=QModelIndex()):
        """Get count of active downloads."""
        if parent.isValid():
            # We don't have children
            return 0
        return len(self)


class TempDownloadManager(QObject):

    """Manager to handle temporary download files.

    The downloads are downloaded to a temporary location and then openened with
    the system standard application. The temporary files are deleted when
    qutebrowser is shutdown.

    Attributes:
        files: A list of NamedTemporaryFiles of downloaded items.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []
        self._tmpdir = None

    def cleanup(self):
        """Clean up any temporary files."""
        if self._tmpdir is not None:
            try:
                self._tmpdir.cleanup()
            except OSError:
                log.misc.exception("Failed to clean up temporary download "
                                   "directory")
            self._tmpdir = None

    def _get_tmpdir(self):
        """Return the temporary directory that is used for downloads.

        The directory is created lazily on first access.

        Return:
            The tempfile.TemporaryDirectory that is used.
        """
        if self._tmpdir is None:
            self._tmpdir = tempfile.TemporaryDirectory(
                prefix='qutebrowser-downloads-')
        return self._tmpdir

    def get_tmpfile(self, suggested_name):
        """Return a temporary file in the temporary downloads directory.

        The files are kept as long as qutebrowser is running and automatically
        cleaned up at program exit.

        Args:
            suggested_name: str of the "suggested"/original filename. Used as a
                            suffix, so any file extenions are preserved.

        Return:
            A tempfile.NamedTemporaryFile that should be used to save the file.
        """
        tmpdir = self._get_tmpdir()
        encoding = sys.getfilesystemencoding()
        suggested_name = utils.force_encoding(suggested_name, encoding)
        # Make sure that the filename is not too long
        suggested_name = utils.elide_filename(suggested_name, 50)
        fobj = tempfile.NamedTemporaryFile(dir=tmpdir.name, delete=False,
                                           suffix=suggested_name)
        self.files.append(fobj)
        return fobj
