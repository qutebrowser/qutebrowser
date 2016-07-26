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

import sip
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, QObject, QTimer,
                          Qt, QVariant, QAbstractListModel, QModelIndex, QUrl)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply
# We need this import so PyQt can use it inside pyqtSlot
from PyQt5.QtWebKitWidgets import QWebPage  # pylint: disable=unused-import

from qutebrowser.config import config
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import (message, usertypes, log, utils, urlutils,
                               objreg, standarddir, qtutils)
from qutebrowser.browser.webkit import http
from qutebrowser.browser.webkit.network import networkmanager


ModelRole = usertypes.enum('ModelRole', ['item'], start=Qt.UserRole,
                           is_int=True)


RetryInfo = collections.namedtuple('RetryInfo', ['request', 'manager'])

DownloadPath = collections.namedtuple('DownloadPath', ['filename', 'question'])

# Remember the last used directory
last_used_directory = None


# All REFRESH_INTERVAL milliseconds, speeds will be recalculated and downloads
# redrawn.
REFRESH_INTERVAL = 500


def download_dir():
    """Get the download directory to use."""
    directory = config.get('storage', 'download-directory')
    remember_dir = config.get('storage', 'remember-download-directory')

    if remember_dir and last_used_directory is not None:
        return last_used_directory
    elif directory is None:
        return standarddir.download()
    else:
        return directory


def path_suggestion(filename):
    """Get the suggested file path.

    Args:
        filename: The filename to use if included in the suggestion.
    """
    suggestion = config.get('completion', 'download-path-suggestion')
    if suggestion == 'path':
        # add trailing '/' if not present
        return os.path.join(download_dir(), '')
    elif suggestion == 'filename':
        return filename
    elif suggestion == 'both':
        return os.path.join(download_dir(), filename)
    else:  # pragma: no cover
        raise ValueError("Invalid suggestion value {}!".format(suggestion))


def create_full_filename(basename, filename):
    """Create a full filename based on the given basename and filename.

    Args:
        basename: The basename to use if filename is a directory.
        filename: The path to a folder or file where you want to save.

    Return:
        The full absolute path, or None if filename creation was not possible.
    """
    # Remove chars which can't be encoded in the filename encoding.
    # See https://github.com/The-Compiler/qutebrowser/issues/427
    encoding = sys.getfilesystemencoding()
    filename = utils.force_encoding(filename, encoding)
    basename = utils.force_encoding(basename, encoding)
    if os.path.isabs(filename) and os.path.isdir(filename):
        # We got an absolute directory from the user, so we save it under
        # the default filename in that directory.
        return os.path.join(filename, basename)
    elif os.path.isabs(filename):
        # We got an absolute filename from the user, so we save it under
        # that filename.
        return filename
    return None


def ask_for_filename(suggested_filename, win_id, *, parent=None,
                     prompt_download_directory=None):
    """Prepare a question for a download-path.

    If a filename can be determined directly, it is returned instead.

    Returns a (filename, question)-namedtuple, in which one component is
    None. filename is a string, question is a usertypes.Question. The
    question has a special .ask() method that takes no arguments for
    convenience, as this function does not yet ask the question, it
    only prepares it.

    Args:
        suggested_filename: The "default"-name that is pre-entered as path.
        win_id: The window where the question will be asked.
        parent: The parent of the question (a QObject).
        prompt_download_directory: If this is something else than None, it
                                   will overwrite the
                                   storage->prompt-download-directory setting.
    """
    if prompt_download_directory is None:
        prompt_download_directory = config.get('storage',
                                               'prompt-download-directory')

    if not prompt_download_directory:
        return DownloadPath(filename=download_dir(), question=None)

    encoding = sys.getfilesystemencoding()
    suggested_filename = utils.force_encoding(suggested_filename, encoding)

    q = usertypes.Question(parent)
    q.text = "Save file to:"
    q.mode = usertypes.PromptMode.text
    q.completed.connect(q.deleteLater)
    q.default = path_suggestion(suggested_filename)

    message_bridge = objreg.get('message-bridge', scope='window',
                                window=win_id)
    q.ask = lambda: message_bridge.ask(q, blocking=False)
    return DownloadPath(filename=None, question=q)


class DownloadItemStats(QObject):

    """Statistics (bytes done, total bytes, time, etc.) about a download.

    Class attributes:
        SPEED_AVG_WINDOW: How many seconds of speed data to average to
                          estimate the remaining time.

    Attributes:
        done: How many bytes there are already downloaded.
        total: The total count of bytes.  None if the total is unknown.
        speed: The current download speed, in bytes per second.
        _speed_avg: A rolling average of speeds.
        _last_done: The count of bytes which where downloaded when calculating
                    the speed the last time.
    """

    SPEED_AVG_WINDOW = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.total = None
        self.done = 0
        self.speed = 0
        self._last_done = 0
        samples = int(self.SPEED_AVG_WINDOW * (1000 / REFRESH_INTERVAL))
        self._speed_avg = collections.deque(maxlen=samples)

    def update_speed(self):
        """Recalculate the current download speed.

        The caller needs to guarantee this is called all REFRESH_INTERVAL ms.
        """
        if self.done is None:
            # this can happen for very fast downloads, e.g. when actually
            # opening a file
            return
        delta = self.done - self._last_done
        self.speed = delta * 1000 / REFRESH_INTERVAL
        self._speed_avg.append(self.speed)
        self._last_done = self.done

    def finish(self):
        """Set the download stats as finished."""
        self.done = self.total

    def percentage(self):
        """The current download percentage, or None if unknown."""
        if self.done == self.total:
            return 100
        elif self.total == 0 or self.total is None:
            return None
        else:
            return 100 * self.done / self.total

    def remaining_time(self):
        """The remaining download time in seconds, or None."""
        if self.total is None or not self._speed_avg:
            # No average yet or we don't know the total size.
            return None
        remaining_bytes = self.total - self.done
        avg = sum(self._speed_avg) / len(self._speed_avg)
        if avg == 0:
            # Download stalled
            return None
        else:
            return remaining_bytes / avg

    @pyqtSlot('qint64', 'qint64')
    def on_download_progress(self, bytes_done, bytes_total):
        """Update local variables when the download progress changed.

        Args:
            bytes_done: How many bytes are downloaded.
            bytes_total: How many bytes there are to download in total.
        """
        if bytes_total == -1:
            bytes_total = None
        self.done = bytes_done
        self.total = bytes_total


class DownloadItem(QObject):

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
        MAX_REDIRECTS: The maximum redirection count.

    Attributes:
        done: Whether the download is finished.
        stats: A DownloadItemStats object.
        index: The index of the download in the view.
        successful: Whether the download has completed successfully.
        error_msg: The current error message, or None
        autoclose: Whether to close the associated file if the download is
                   done.
        fileobj: The file object to download the file to.
        reply: The QNetworkReply associated with this download.
        retry_info: A RetryInfo instance.
        raw_headers: The headers sent by the server.
        _filename: The filename of the download.
        _redirects: How many time we were redirected already.
        _buffer: A BytesIO object to buffer incoming data until we know the
                 target file.
        _read_timer: A Timer which reads the QNetworkReply into self._buffer
                     periodically.
        _win_id: The window ID the DownloadItem runs in.
        _dead: Whether the Download has _die()'d.

    Signals:
        data_changed: The downloads metadata changed.
        finished: The download was finished.
        cancelled: The download was cancelled.
        error: An error with the download occurred.
               arg: The error message as string.
        redirected: Signal emitted when a download was redirected.
            arg 0: The new QNetworkRequest.
            arg 1: The old QNetworkReply.
        do_retry: Emitted when a download is retried.
            arg 0: The new DownloadItem
    """

    MAX_REDIRECTS = 10
    data_changed = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)
    cancelled = pyqtSignal()
    redirected = pyqtSignal(QNetworkRequest, QNetworkReply)
    do_retry = pyqtSignal(object)  # DownloadItem

    def __init__(self, reply, win_id, parent=None):
        """Constructor.

        Args:
            reply: The QNetworkReply to download.
        """
        super().__init__(parent)
        self.retry_info = None
        self.done = False
        self.stats = DownloadItemStats(self)
        self.index = 0
        self.autoclose = True
        self.reply = None
        self._buffer = io.BytesIO()
        self._read_timer = usertypes.Timer(self, name='download-read-timer')
        self._read_timer.setInterval(500)
        self._read_timer.timeout.connect(self.on_read_timer_timeout)
        self._redirects = 0
        self.error_msg = None
        self.basename = '???'
        self.successful = False
        self.fileobj = None
        self._filename = None
        self.init_reply(reply)
        self._win_id = win_id
        self.raw_headers = {}
        self._dead = False

    def __repr__(self):
        return utils.get_repr(self, basename=self.basename)

    def __str__(self):
        """Get the download as a string.

        Example: foo.pdf [699.2kB/s|0.34|16%|4.253/25.124]
        """
        speed = utils.format_size(self.stats.speed, suffix='B/s')
        down = utils.format_size(self.stats.done, suffix='B')
        perc = self.stats.percentage()
        remaining = self.stats.remaining_time()
        if self.error_msg is None:
            errmsg = ""
        else:
            errmsg = " - {}".format(self.error_msg)
        if all(e is None for e in [perc, remaining, self.stats.total]):
            return ('{index}: {name} [{speed:>10}|{down}]{errmsg}'.format(
                index=self.index, name=self.basename, speed=speed,
                down=down, errmsg=errmsg))
        if perc is None:
            perc = '??'
        else:
            perc = round(perc)
        if remaining is None:
            remaining = '?'
        else:
            remaining = utils.format_seconds(remaining)
        total = utils.format_size(self.stats.total, suffix='B')
        if self.done:
            return ('{index}: {name} [{perc:>2}%|{total}]{errmsg}'.format(
                index=self.index, name=self.basename, perc=perc,
                total=total, errmsg=errmsg))
        else:
            return ('{index}: {name} [{speed:>10}|{remaining:>5}|{perc:>2}%|'
                    '{down}/{total}]{errmsg}'.format(
                        index=self.index, name=self.basename, speed=speed,
                        remaining=remaining, perc=perc, down=down,
                        total=total, errmsg=errmsg))

    def _create_fileobj(self):
        """Create a file object using the internal filename."""
        try:
            fileobj = open(self._filename, 'wb')
        except OSError as e:
            self._die(e.strerror)
        else:
            self.set_fileobj(fileobj)

    def _ask_confirm_question(self, msg):
        """Create a Question object to be asked."""
        q = usertypes.Question(self)
        q.text = msg
        q.mode = usertypes.PromptMode.yesno
        q.answered_yes.connect(self._create_fileobj)
        q.answered_no.connect(functools.partial(self.cancel, False))
        q.cancelled.connect(functools.partial(self.cancel, False))
        self.cancelled.connect(q.abort)
        self.error.connect(q.abort)
        message_bridge = objreg.get('message-bridge', scope='window',
                                    window=self._win_id)
        message_bridge.ask(q, blocking=False)

    def _die(self, msg):
        """Abort the download and emit an error."""
        assert not self.successful
        # Prevent actions if calling _die() twice. This might happen if the
        # error handler correctly connects, and the error occurs in init_reply
        # between reply.error.connect and the reply.error() check. In this
        # case, the connected error handlers will be called twice, once via the
        # direct error.emit() and once here in _die(). The stacks look like
        # this then:
        #   <networkmanager error.emit> -> on_reply_error -> _die ->
        #   self.error.emit()
        # and
        #   [init_reply -> <single shot timer> ->] <lambda in init_reply> ->
        #   self.error.emit()
        # which may lead to duplicate error messages (and failing tests)
        if self._dead:
            return
        self._dead = True
        self._read_timer.stop()
        self.reply.downloadProgress.disconnect()
        self.reply.finished.disconnect()
        self.reply.error.disconnect()
        self.reply.readyRead.disconnect()
        self.error_msg = msg
        self.stats.finish()
        self.error.emit(msg)
        with log.hide_qt_warning('QNetworkReplyImplPrivate::error: Internal '
                                 'problem, this method must only be called '
                                 'once.'):
            # See https://codereview.qt-project.org/#/c/107863/
            self.reply.abort()
        self.reply.deleteLater()
        self.reply = None
        self.done = True
        self.data_changed.emit()
        if self.fileobj is not None:
            try:
                self.fileobj.close()
            except OSError:
                log.downloads.exception("Error while closing file object")

    def init_reply(self, reply):
        """Set a new reply and connect its signals.

        Args:
            reply: The QNetworkReply to handle.
        """
        self.done = False
        self.successful = False
        self.reply = reply
        reply.setReadBufferSize(16 * 1024 * 1024)  # 16 MB
        reply.downloadProgress.connect(self.stats.on_download_progress)
        reply.finished.connect(self.on_reply_finished)
        reply.error.connect(self.on_reply_error)
        reply.readyRead.connect(self.on_ready_read)
        reply.metaDataChanged.connect(self.on_meta_data_changed)
        self.retry_info = RetryInfo(request=reply.request(),
                                    manager=reply.manager())
        if not self.fileobj:
            self._read_timer.start()
        # We could have got signals before we connected slots to them.
        # Here no signals are connected to the DownloadItem yet, so we use a
        # singleShot QTimer to emit them after they are connected.
        if reply.error() != QNetworkReply.NoError:
            QTimer.singleShot(0, lambda: self._die(reply.errorString()))

    def get_status_color(self, position):
        """Choose an appropriate color for presenting the download's status.

        Args:
            position: The color type requested, can be 'fg' or 'bg'.
        """
        # pylint: disable=bad-config-call
        # WORKAROUND for https://bitbucket.org/logilab/astroid/issue/104/
        assert position in ["fg", "bg"]
        start = config.get('colors', 'downloads.{}.start'.format(position))
        stop = config.get('colors', 'downloads.{}.stop'.format(position))
        system = config.get('colors', 'downloads.{}.system'.format(position))
        error = config.get('colors', 'downloads.{}.error'.format(position))
        if self.error_msg is not None:
            assert not self.successful
            return error
        elif self.stats.percentage() is None:
            return start
        else:
            return utils.interpolate_color(start, stop,
                                           self.stats.percentage(), system)

    @pyqtSlot()
    def cancel(self, remove_data=True):
        """Cancel the download.

        Args:
            remove_data: Whether to remove the downloaded data.
        """
        log.downloads.debug("cancelled")
        self._read_timer.stop()
        self.cancelled.emit()
        if self.reply is not None:
            self.reply.finished.disconnect(self.on_reply_finished)
            self.reply.abort()
            self.reply.deleteLater()
            self.reply = None
        if self.fileobj is not None:
            self.fileobj.close()
        if remove_data:
            self.delete()
        self.done = True
        self.finished.emit()
        self.data_changed.emit()

    def delete(self):
        """Delete the downloaded file."""
        try:
            if self._filename is not None and os.path.exists(self._filename):
                os.remove(self._filename)
        except OSError:
            log.downloads.exception("Failed to remove partial file")

    @pyqtSlot()
    def retry(self):
        """Retry a failed download."""
        assert self.done
        assert not self.successful
        download_manager = objreg.get('download-manager', scope='window',
                                      window=self._win_id)
        new_reply = self.retry_info.manager.get(self.retry_info.request)
        new_download = download_manager.fetch(
            new_reply, suggested_filename=self.basename)
        self.do_retry.emit(new_download)
        self.cancel()

    @pyqtSlot()
    def open_file(self):
        """Open the downloaded file."""
        assert self.successful
        filename = self._filename
        if filename is None:
            filename = getattr(self.fileobj, 'name', None)
        if filename is None:
            log.downloads.error("No filename to open the download!")
            return
        url = QUrl.fromLocalFile(filename)
        QDesktopServices.openUrl(url)

    def set_filename(self, filename):
        """Set the filename to save the download to.

        Args:
            filename: The full filename to save the download to.
                      None: special value to stop the download.
        """
        global last_used_directory
        if self.fileobj is not None:  # pragma: no cover
            raise ValueError("fileobj was already set! filename: {}, "
                             "existing: {}, fileobj {}".format(
                                 filename, self._filename, self.fileobj))
        filename = os.path.expanduser(filename)
        self._filename = create_full_filename(self.basename, filename)
        if self._filename is None:
            # We only got a filename (without directory) or a relative path
            # from the user, so we append that to the default directory and
            # try again.
            self._filename = create_full_filename(
                self.basename, os.path.join(download_dir(), filename))

        # At this point, we have a misconfigured XDG_DOWNLOAD_DIR, as
        # download_dir() + filename is still no absolute path.
        # The config value is checked for "absoluteness", but
        # ~/.config/user-dirs.dirs may be misconfigured and a non-absolute path
        # may be set for XDG_DOWNLOAD_DIR
        if self._filename is None:
            message.error(
                self._win_id,
                "XDG_DOWNLOAD_DIR points to a relative path - please check"
                " your ~/.config/user-dirs.dirs. The download is saved in"
                " your home directory.",
            )
            # fall back to $HOME as download_dir
            self._filename = create_full_filename(
                self.basename, os.path.expanduser(os.path.join('~', filename)))

        self.basename = os.path.basename(self._filename)
        last_used_directory = os.path.dirname(self._filename)

        log.downloads.debug("Setting filename to {}".format(filename))
        if os.path.isfile(self._filename):
            # The file already exists, so ask the user if it should be
            # overwritten.
            txt = self._filename + " already exists. Overwrite?"
            self._ask_confirm_question(txt)
        # FIFO, device node, etc. Make sure we want to do this
        elif (os.path.exists(self._filename) and
              not os.path.isdir(self._filename)):
            txt = (self._filename + " already exists and is a special file. "
                   "Write to this?")
            self._ask_confirm_question(txt)
        else:
            self._create_fileobj()

    def set_fileobj(self, fileobj):
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
            if self.reply.isFinished():
                # Downloading to the buffer in RAM has already finished so we
                # write out the data and clean up now.
                self.on_reply_finished()
            else:
                # Since the buffer already might be full, on_ready_read might
                # not be called at all anymore, so we force it here to flush
                # the buffer and continue receiving new data.
                self.on_ready_read()
        except OSError as e:
            self._die(e.strerror)

    def finish_download(self):
        """Write buffered data to disk and finish the QNetworkReply."""
        log.downloads.debug("Finishing download...")
        if self.reply.isOpen():
            self.fileobj.write(self.reply.readAll())
        if self.autoclose:
            self.fileobj.close()
        self.successful = self.reply.error() == QNetworkReply.NoError
        self.reply.close()
        self.reply.deleteLater()
        self.reply = None
        self.finished.emit()
        self.done = True
        log.downloads.debug("Download finished")
        self.data_changed.emit()

    @pyqtSlot()
    def on_reply_finished(self):
        """Clean up when the download was finished.

        Note when this gets called, only the QNetworkReply has finished. This
        doesn't mean the download (i.e. writing data to the disk) is finished
        as well. Therefore, we can't close() the QNetworkReply in here yet.
        """
        if self.reply is None:
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
            self.finish_download()

    @pyqtSlot()
    def on_ready_read(self):
        """Read available data and save file when ready to read."""
        if self.fileobj is None or self.reply is None:
            # No filename has been set yet (so we don't empty the buffer) or we
            # got a readyRead after the reply was finished (which happens on
            # qute:log for example).
            return
        if not self.reply.isOpen():
            raise OSError("Reply is closed!")
        try:
            self.fileobj.write(self.reply.readAll())
        except OSError as e:
            self._die(e.strerror)

    @pyqtSlot('QNetworkReply::NetworkError')
    def on_reply_error(self, code):
        """Handle QNetworkReply errors."""
        if code == QNetworkReply.OperationCanceledError:
            return
        else:
            self._die(self.reply.errorString())

    @pyqtSlot()
    def on_read_timer_timeout(self):
        """Read some bytes from the QNetworkReply periodically."""
        if not self.reply.isOpen():
            raise OSError("Reply is closed!")
        data = self.reply.read(1024)
        if data is not None:
            self._buffer.write(data)

    @pyqtSlot()
    def on_meta_data_changed(self):
        """Update the download's metadata."""
        if self.reply is None:
            return
        self.raw_headers = {}
        for key, value in self.reply.rawHeaderPairs():
            self.raw_headers[bytes(key)] = bytes(value)

    def _handle_redirect(self):
        """Handle an HTTP redirect.

        Return:
            True if the download was redirected, False otherwise.
        """
        redirect = self.reply.attribute(
            QNetworkRequest.RedirectionTargetAttribute)
        if redirect is None or redirect.isEmpty():
            return False
        new_url = self.reply.url().resolved(redirect)
        request = self.reply.request()
        if new_url == request.url():
            return False

        if self._redirects > self.MAX_REDIRECTS:
            self._die("Maximum redirection count reached!")
            return True  # so on_reply_finished aborts

        log.downloads.debug("{}: Handling redirect".format(self))
        self._redirects += 1
        request.setUrl(new_url)
        reply = self.reply
        reply.finished.disconnect(self.on_reply_finished)
        self._read_timer.stop()
        self.reply = None
        if self.fileobj is not None:
            self.fileobj.seek(0)
        self.redirected.emit(request, reply)  # this will change self.reply!
        reply.deleteLater()  # the old one
        return True


class DownloadManager(QAbstractListModel):

    """Manager and model for currently running downloads.

    Attributes:
        downloads: A list of active DownloadItems.
        questions: A list of Question objects to not GC them.
        _networkmanager: A NetworkManager for generic downloads.
        _win_id: The window ID the DownloadManager runs in.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self.downloads = []
        self.questions = []
        self._networkmanager = networkmanager.NetworkManager(
            win_id, None, self)
        self._update_timer = usertypes.Timer(self, 'download-update')
        self._update_timer.timeout.connect(self.update_gui)
        self._update_timer.setInterval(REFRESH_INTERVAL)

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
    def update_gui(self):
        """Periodical GUI update of all items."""
        assert self.downloads
        for dl in self.downloads:
            dl.stats.update_speed()
        self.dataChanged.emit(self.index(0), self.last_index())

    @pyqtSlot('QUrl', 'QWebPage')
    def get(self, url, **kwargs):
        """Start a download with a link URL.

        Args:
            url: The URL to get, as QUrl
            **kwargs: passed to get_request().

        Return:
            The created DownloadItem.
        """
        if not url.isValid():
            urlutils.invalid_url_error(self._win_id, url, "start download")
            return
        req = QNetworkRequest(url)
        return self.get_request(req, **kwargs)

    def get_request(self, request, *, target=None, **kwargs):
        """Start a download with a QNetworkRequest.

        Args:
            request: The QNetworkRequest to download.
            target: Where to save the download as usertypes.DownloadTarget.
            **kwargs: Passed to fetch_request.

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

        return self.fetch_request(request,
                                  target=target,
                                  suggested_filename=suggested_fn,
                                  **kwargs)

    def fetch_request(self, request, *, page=None, **kwargs):
        """Download a QNetworkRequest to disk.

        Args:
            request: The QNetworkRequest to download.
            page: The QWebPage to use.
            **kwargs: passed to fetch().

        Return:
            The created DownloadItem.
        """
        if page is None:
            nam = self._networkmanager
        else:
            nam = page.networkAccessManager()
        reply = nam.get(request)
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
        download.cancelled.connect(
            functools.partial(self.remove_item, download))

        delay = config.get('ui', 'remove-finished-downloads')
        if delay > -1:
            download.finished.connect(
                functools.partial(self.remove_item_delayed, download, delay))
        elif auto_remove:
            download.finished.connect(
                functools.partial(self.remove_item, download))

        download.data_changed.connect(
            functools.partial(self.on_data_changed, download))
        download.error.connect(self.on_error)
        download.redirected.connect(
            functools.partial(self.on_redirect, download))
        download.basename = suggested_filename
        idx = len(self.downloads)
        download.index = idx + 1  # "Human readable" index
        self.beginInsertRows(QModelIndex(), idx, idx)
        self.downloads.append(download)
        self.endInsertRows()

        if not self._update_timer.isActive():
            self._update_timer.start()

        if target is not None:
            self._set_download_target(download, suggested_filename, target)
            return download

        # Neither filename nor fileobj were given, prepare a question
        filename, q = ask_for_filename(
            suggested_filename, self._win_id, parent=self,
            prompt_download_directory=prompt_download_directory,
        )

        # User doesn't want to be asked, so just use the download_dir
        if filename is not None:
            target = usertypes.FileDownloadTarget(filename)
            self._set_download_target(download, suggested_filename, target)
            return download

        # Ask the user for a filename
        self._postprocess_question(q)
        q.answered.connect(
            functools.partial(self._set_download_target, download,
                              suggested_filename))
        q.cancelled.connect(download.cancel)
        download.cancelled.connect(q.abort)
        download.error.connect(q.abort)
        q.ask()

        return download

    def _set_download_target(self, download, suggested_filename, target):
        """Set the target for a given download.

        Args:
            download: The download to set the filename for.
            suggested_filename: The suggested filename.
            target: The usertypes.DownloadTarget for this download.
        """
        if isinstance(target, usertypes.FileObjDownloadTarget):
            download.set_fileobj(target.fileobj)
            download.autoclose = False
        elif isinstance(target, usertypes.FileDownloadTarget):
            download.set_filename(target.filename)
        elif isinstance(target, usertypes.OpenFileDownloadTarget):
            tmp_manager = objreg.get('temporary-downloads')
            fobj = tmp_manager.get_tmpfile(suggested_filename)
            download.finished.connect(download.open_file)
            download.autoclose = True
            download.set_fileobj(fobj)
        else:
            log.downloads.error("Unknown download target: {}".format(target))

    def raise_no_download(self, count):
        """Raise an exception that the download doesn't exist.

        Args:
            count: The index of the download
        """
        if not count:
            raise cmdexc.CommandError("There's no download!")
        raise cmdexc.CommandError("There's no download {}!".format(count))

    @cmdutils.register(instance='download-manager', scope='window')
    @cmdutils.argument('count', count=True)
    def download_cancel(self, all_=False, count=0):
        """Cancel the last/[count]th download.

        Args:
            all_: Cancel all running downloads
            count: The index of the download to cancel.
        """
        if all_:
            # We need to make a copy as we're indirectly mutating
            # self.downloads here
            for download in self.downloads[:]:
                if not download.done:
                    download.cancel()
        else:
            try:
                download = self.downloads[count - 1]
            except IndexError:
                self.raise_no_download(count)
            if download.done:
                if not count:
                    count = len(self.downloads)
                raise cmdexc.CommandError("Download {} is already done!"
                                        .format(count))
            download.cancel()

    @cmdutils.register(instance='download-manager', scope='window')
    @cmdutils.argument('count', count=True)
    def download_delete(self, count=0):
        """Delete the last/[count]th download from disk.

        Args:
            count: The index of the download to delete.
        """
        try:
            download = self.downloads[count - 1]
        except IndexError:
            self.raise_no_download(count)
        if not download.successful:
            if not count:
                count = len(self.downloads)
            raise cmdexc.CommandError("Download {} is not done!".format(count))
        download.delete()
        self.remove_item(download)
        log.downloads.debug("deleted download {}".format(download))

    @cmdutils.register(instance='download-manager', scope='window')
    @cmdutils.argument('count', count=True)
    def download_open(self, count=0):
        """Open the last/[count]th download.

        Args:
            count: The index of the download to open.
        """
        try:
            download = self.downloads[count - 1]
        except IndexError:
            self.raise_no_download(count)
        if not download.successful:
            if not count:
                count = len(self.downloads)
            raise cmdexc.CommandError("Download {} is not done!".format(count))
        download.open_file()

    @cmdutils.register(instance='download-manager', scope='window')
    @cmdutils.argument('count', count=True)
    def download_retry(self, count=0):
        """Retry the first failed/[count]th download.

        Args:
            count: The index of the download to retry.
        """
        if count:
            try:
                download = self.downloads[count - 1]
            except IndexError:
                self.raise_no_download(count)
            if download.successful or not download.done:
                raise cmdexc.CommandError("Download {} did not fail!".format(
                    count))
        else:
            to_retry = [d for d in self.downloads
                        if d.done and not d.successful]
            if not to_retry:
                raise cmdexc.CommandError("No failed downloads!")
            else:
                download = to_retry[0]
        download.retry()

    @pyqtSlot(QNetworkRequest, QNetworkReply)
    def on_redirect(self, download, request, reply):
        """Handle an HTTP redirect of a download.

        Args:
            download: The old DownloadItem.
            request: The new QNetworkRequest.
            reply: The old QNetworkReply.
        """
        log.downloads.debug("redirected: {} -> {}".format(
            reply.url(), request.url()))
        new_reply = reply.manager().get(request)
        download.init_reply(new_reply)

    @pyqtSlot(DownloadItem)
    def on_data_changed(self, download):
        """Emit data_changed signal when download data changed."""
        try:
            idx = self.downloads.index(download)
        except ValueError:
            # download has been deleted in the meantime
            return
        model_idx = self.index(idx, 0)
        qtutils.ensure_valid(model_idx)
        self.dataChanged.emit(model_idx, model_idx)

    @pyqtSlot(str)
    def on_error(self, msg):
        """Display error message on download errors."""
        message.error(self._win_id, "Download error: {}".format(msg))

    def has_downloads_with_nam(self, nam):
        """Check if the DownloadManager has any downloads with the given QNAM.

        Args:
            nam: The QNetworkAccessManager to check.

        Return:
            A boolean.
        """
        assert nam.adopted_downloads == 0
        for download in self.downloads:
            running_download = (download.reply is not None and
                                download.reply.manager() is nam)
            # user could request retry after tab is closed.
            failed_download = (download.done and (not download.successful) and
                               download.retry_info.manager is nam)
            if running_download or failed_download:
                nam.adopt_download(download)
        return nam.adopted_downloads

    def can_clear(self):
        """Check if there are finished downloads to clear."""
        return any(download.done for download in self.downloads)

    @cmdutils.register(instance='download-manager', scope='window')
    def download_clear(self):
        """Remove all finished downloads from the list."""
        finished_items = [d for d in self.downloads if d.done]
        self.remove_items(finished_items)

    @cmdutils.register(instance='download-manager', scope='window')
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
                download = self.downloads[count - 1]
            except IndexError:
                self.raise_no_download(count)
            if not download.done:
                if not count:
                    count = len(self.downloads)
                raise cmdexc.CommandError("Download {} is not done!"
                                          .format(count))
            self.remove_item(download)

    def last_index(self):
        """Get the last index in the model.

        Return:
            A (possibly invalid) QModelIndex.
        """
        idx = self.index(self.rowCount() - 1)
        return idx

    def remove_item(self, download):
        """Remove a given download."""
        if sip.isdeleted(self):
            # https://github.com/The-Compiler/qutebrowser/issues/1242
            return
        try:
            idx = self.downloads.index(download)
        except ValueError:
            # already removed
            return
        self.beginRemoveRows(QModelIndex(), idx, idx)
        del self.downloads[idx]
        self.endRemoveRows()
        download.deleteLater()
        self.update_indexes()
        if not self.downloads:
            self._update_timer.stop()

    def remove_item_delayed(self, download, delay):
        """Remove a given download after a short delay."""
        QTimer.singleShot(delay, functools.partial(self.remove_item, download))

    def remove_items(self, downloads):
        """Remove an iterable of downloads."""
        # On the first pass, we only generate the indices so we get the
        # first/last one for beginRemoveRows.
        indices = []
        # We need to iterate over downloads twice, which won't work if it's a
        # generator.
        downloads = list(downloads)
        for download in downloads:
            try:
                indices.append(self.downloads.index(download))
            except ValueError:
                # already removed
                pass
        if not indices:
            return
        indices.sort()
        self.beginRemoveRows(QModelIndex(), indices[0], indices[-1])
        for download in downloads:
            try:
                self.downloads.remove(download)
            except ValueError:
                # already removed
                pass
            else:
                download.deleteLater()
        self.endRemoveRows()
        if not self.downloads:
            self._update_timer.stop()

    def update_indexes(self):
        """Update indexes of all DownloadItems."""
        first_idx = None
        for i, d in enumerate(self.downloads, 1):
            if first_idx is None and d.index != i:
                first_idx = i - 1
            d.index = i
        if first_idx is not None:
            model_idx = self.index(first_idx, 0)
            qtutils.ensure_valid(model_idx)
            self.dataChanged.emit(model_idx, self.last_index())

    def headerData(self, section, orientation, role):
        """Simple constant header."""
        if (section == 0 and orientation == Qt.Horizontal and
                role == Qt.DisplayRole):
            return "Downloads"
        else:
            return ""

    def data(self, index, role):
        """Download data from DownloadManager."""
        qtutils.ensure_valid(index)
        if index.parent().isValid() or index.column() != 0:
            return QVariant()

        item = self.downloads[index.row()]
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
                data = QVariant()
            else:
                return item.error_msg
        else:
            data = QVariant()
        return data

    def flags(self, _index):
        """Override flags so items aren't selectable.

        The default would be Qt.ItemIsEnabled | Qt.ItemIsSelectable.
        """
        return Qt.ItemIsEnabled | Qt.ItemNeverHasChildren

    def rowCount(self, parent=QModelIndex()):
        """Get count of active downloads."""
        if parent.isValid():
            # We don't have children
            return 0
        return len(self.downloads)

    def running_downloads(self):
        """Return the amount of still running downloads.

        Return:
            The number of unfinished downloads.
        """
        return sum(1 for download in self.downloads if not download.done)


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
            self._tmpdir.cleanup()
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
        fobj = tempfile.NamedTemporaryFile(dir=tmpdir.name, delete=False,
                                           suffix=suggested_name)
        self.files.append(fobj)
        return fobj
