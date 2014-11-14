# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os
import os.path
import functools
import collections

from PyQt5.QtCore import (pyqtSlot, pyqtSignal, QObject, QTimer,
                          QStandardPaths, Qt, QVariant, QAbstractListModel,
                          QModelIndex)
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply
# We need this import so PyQt can use it inside pyqtSlot
from PyQt5.QtWebKitWidgets import QWebPage  # pylint: disable=unused-import

from qutebrowser.config import config
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import (message, http, usertypes, log, utils, urlutils,
                               objreg, standarddir, qtutils)


ModelRole = usertypes.enum('ModelRole', ['item'], start=Qt.UserRole,
                           is_int=True)


class DownloadItem(QObject):

    """A single download currently running.

    Class attributes:
        SPEED_REFRESH_INTERVAL: How often to refresh the speed, in msec.
        SPEED_AVG_WINDOW: How many seconds of speed data to average to
                          estimate the remaining time.

    Attributes:
        successful: Whether the download has completed sucessfully.
        error_msg: The current error message, or None
        _bytes_done: How many bytes there are already downloaded.
        _bytes_total: The total count of bytes.
                      None if the total is unknown.
        _speed: The current download speed, in bytes per second.
        _fileobj: The file object to download the file to.
        _filename: The filename of the download.
        _is_cancelled: Whether the download was cancelled.
        _speed_avg: A rolling average of speeds.
        _reply: The QNetworkReply associated with this download.
        _last_done: The count of bytes which where downloaded when calculating
                    the speed the last time.

    Signals:
        data_changed: The downloads metadata changed.
        finished: The download was finished.
        cancelled: The download was cancelled.
        error: An error with the download occured.
               arg: The error message as string.
    """

    SPEED_REFRESH_INTERVAL = 500
    SPEED_AVG_WINDOW = 30
    data_changed = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, reply, parent=None):
        """Constructor.

        Args:
            reply: The QNetworkReply to download.
        """
        super().__init__(parent)
        self._reply = reply
        self._bytes_total = None
        self._speed = 0
        self.error_msg = None
        self.basename = '???'
        self.successful = False
        samples = int(self.SPEED_AVG_WINDOW *
                      (1000 / self.SPEED_REFRESH_INTERVAL))
        self._speed_avg = collections.deque(maxlen=samples)
        self._fileobj = None
        self._filename = None
        self._is_cancelled = False
        self._do_delayed_write = False
        self._bytes_done = 0
        self._last_done = 0
        reply.setReadBufferSize(16 * 1024 * 1024)
        reply.downloadProgress.connect(self.on_download_progress)
        reply.finished.connect(self.on_reply_finished)
        reply.error.connect(self.on_reply_error)
        reply.readyRead.connect(self.on_ready_read)
        # We could have got signals before we connected slots to them.
        # Here no signals are connected to the DownloadItem yet, so we use a
        # singleShot QTimer to emit them after they are connected.
        if reply.error() != QNetworkReply.NoError:
            QTimer.singleShot(0, lambda: self.error.emit(reply.errorString()))
        if reply.isFinished():
            self.successful = reply.error() != QNetworkReply.NoError
            QTimer.singleShot(0, self.finished.emit)
        self.timer = usertypes.Timer(self, 'speed_refresh')
        self.timer.timeout.connect(self.update_speed)
        self.timer.setInterval(self.SPEED_REFRESH_INTERVAL)
        self.timer.start()

    def __repr__(self):
        return utils.get_repr(self, basename=self.basename)

    def __str__(self):
        """Get the download as a string.

        Example: foo.pdf [699.2kB/s|0.34|16%|4.253/25.124]
        """
        speed = utils.format_size(self._speed, suffix='B/s')
        down = utils.format_size(self._bytes_done, suffix='B')
        perc = self._percentage()
        remaining = self._remaining_time()
        if self.error_msg is None:
            errmsg = ""
        else:
            errmsg = " - {}".format(self.error_msg)
        if all(e is None for e in (perc, remaining, self._bytes_total)):
            return ('{name} [{speed:>10}|{down}]{errmsg}'.format(
                name=self.basename, speed=speed, down=down, errmsg=errmsg))
        if perc is None:
            perc = '??'
        else:
            perc = round(perc)
        if remaining is None:
            remaining = '?'
        else:
            remaining = utils.format_seconds(remaining)
        total = utils.format_size(self._bytes_total, suffix='B')
        return ('{name} [{speed:>10}|{remaining:>5}|{perc:>2}%|'
                '{down}/{total}]{errmsg}'.format(
                    name=self.basename, speed=speed, remaining=remaining,
                    perc=perc, down=down, total=total, errmsg=errmsg))

    def _die(self, msg):
        """Abort the download and emit an error."""
        self._reply.downloadProgress.disconnect()
        self._reply.finished.disconnect()
        self._reply.error.disconnect()
        self._reply.readyRead.disconnect()
        self.error_msg = msg
        self._bytes_done = self._bytes_total
        self.timer.stop()
        self.error.emit(msg)
        self._reply.abort()
        self._reply.deleteLater()
        self._reply = None
        if self._fileobj is not None:
            try:
                self._fileobj.close()
            except OSError as e:
                self.error.emit(e.strerror)
        self.data_changed.emit()

    def _percentage(self):
        """The current download percentage, or None if unknown."""
        if self._bytes_total == 0 or self._bytes_total is None:
            return None
        else:
            return 100 * self._bytes_done / self._bytes_total

    def _remaining_time(self):
        """The remaining download time in seconds, or None."""
        if self._bytes_total is None or not self._speed_avg:
            # No average yet or we don't know the total size.
            return None
        remaining_bytes = self._bytes_total - self._bytes_done
        avg = sum(self._speed_avg) / len(self._speed_avg)
        if avg == 0:
            # Download stalled
            return None
        else:
            return remaining_bytes / avg

    def bg_color(self):
        """Background color to be shown."""
        start = config.get('colors', 'downloads.bg.start')
        stop = config.get('colors', 'downloads.bg.stop')
        system = config.get('colors', 'downloads.bg.system')
        error = config.get('colors', 'downloads.bg.error')
        if self.error_msg is not None:
            return error
        elif self._percentage() is None:
            return start
        else:
            return utils.interpolate_color(start, stop, self._percentage(),
                                           system)

    def cancel(self):
        """Cancel the download."""
        log.downloads.debug("cancelled")
        self.cancelled.emit()
        self._is_cancelled = True
        if self._reply is not None:
            self._reply.abort()
            self._reply.deleteLater()
        if self._fileobj is not None:
            self._fileobj.close()
        if self._filename is not None and os.path.exists(self._filename):
            os.remove(self._filename)
        self.finished.emit()

    def set_filename(self, filename):
        """Set the filename to save the download to.

        Args:
            filename: The full filename to save the download to.
                      None: special value to stop the download.
        """
        if self._filename is not None:
            raise ValueError("Filename was already set! filename: {}, "
                             "existing: {}".format(filename, self._filename))
        filename = os.path.expanduser(filename)
        if os.path.isabs(filename) and os.path.isdir(filename):
            # We got an absolute directory from the user, so we save it under
            # the default filename in that directory.
            self._filename = os.path.join(filename, self.basename)
        elif os.path.isabs(filename):
            # We got an absolute filename from the user, so we save it under
            # that filename.
            self._filename = filename
            self.basename = os.path.basename(self._filename)
        else:
            # We only got a filename (without directory) from the user, so we
            # save it under that filename in the default directory.
            download_dir = config.get('storage', 'download-directory')
            if download_dir is None:
                download_dir = standarddir.get(
                    QStandardPaths.DownloadLocation)
            self._filename = os.path.join(download_dir, filename)
            self.basename = filename
        log.downloads.debug("Setting filename to {}".format(filename))
        try:
            self._fileobj = open(self._filename, 'wb')
            if self._do_delayed_write:
                # Downloading to the buffer in RAM has already finished so we
                # write out the data and clean up now.
                self.delayed_write()
            else:
                # Since the buffer already might be full, on_ready_read might
                # not be called at all anymore, so we force it here to flush
                # the buffer and continue receiving new data.
                self.on_ready_read()
        except OSError as e:
            self._die(e.strerror)

    def delayed_write(self):
        """Write buffered data to disk and finish the QNetworkReply."""
        log.downloads.debug("Doing delayed write...")
        self._do_delayed_write = False
        if self._reply.isOpen():
            self._fileobj.write(self._reply.readAll())
        self._fileobj.close()
        self._reply.close()
        self._reply.deleteLater()
        self.successful = True
        self.finished.emit()
        log.downloads.debug("Download finished")

    @pyqtSlot(int, int)
    def on_download_progress(self, bytes_done, bytes_total):
        """Upload local variables when the download progress changed.

        Args:
            bytes_done: How many bytes are downloaded.
            bytes_total: How many bytes there are to download in total.
        """
        if bytes_total == -1:
            bytes_total = None
        self._bytes_done = bytes_done
        self._bytes_total = bytes_total
        self.data_changed.emit()

    @pyqtSlot()
    def on_reply_finished(self):
        """Clean up when the download was finished.

        Note when this gets called, only the QNetworkReply has finished. This
        doesn't mean the download (i.e. writing data to the disk) is finished
        as well. Therefore, we can't close() the QNetworkReply in here yet.
        """
        self._bytes_done = self._bytes_total
        self.timer.stop()
        if self._is_cancelled:
            return
        log.downloads.debug("Reply finished, fileobj {}".format(self._fileobj))
        if self._fileobj is None:
            # We'll handle emptying the buffer and cleaning up as soon as the
            # filename is set.
            self._do_delayed_write = True
        else:
            # We can do a "delayed" write immediately to empty the buffer and
            # clean up.
            self.delayed_write()

    @pyqtSlot()
    def on_ready_read(self):
        """Read available data and save file when ready to read."""
        if self._fileobj is None:
            # No filename has been set yet, so we don't empty the buffer.
            return
        try:
            self._fileobj.write(self._reply.readAll())
        except OSError as e:
            self._die(e.strerror)

    @pyqtSlot(int)
    def on_reply_error(self, code):
        """Handle QNetworkReply errors."""
        if code == QNetworkReply.OperationCanceledError:
            return
        else:
            self.error.emit(self._reply.errorString())

    @pyqtSlot()
    def update_speed(self):
        """Recalculate the current download speed."""
        delta = self._bytes_done - self._last_done
        self._speed = delta * 1000 / self.SPEED_REFRESH_INTERVAL
        self._speed_avg.append(self._speed)
        self._last_done = self._bytes_done
        self.data_changed.emit()


class DownloadManager(QAbstractListModel):

    """Manager and model for currently running downloads.

    Attributes:
        downloads: A list of active DownloadItems.
        questions: A list of Question objects to not GC them.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self.downloads = []
        self.questions = []

    def __repr__(self):
        return utils.get_repr(self, downloads=len(self.downloads))

    @pyqtSlot('QUrl', 'QWebPage')
    def get(self, url, page):
        """Start a download with a link URL.

        Args:
            url: The URL to get, as QUrl
            page: The QWebPage to get the download from.
        """
        if not url.isValid():
            urlutils.invalid_url_error(self._win_id, url, "start download")
            return
        req = QNetworkRequest(url)
        reply = page.networkAccessManager().get(req)
        self.fetch(reply)

    @cmdutils.register(instance='download-manager', scope='window')
    def cancel_download(self, count: {'special': 'count'}=1):
        """Cancel the first/[count]th download.

        Args:
            count: The index of the download to cancel.
        """
        if count == 0:
            return
        try:
            download = self.downloads[count - 1]
        except IndexError:
            raise cmdexc.CommandError("There's no download {}!".format(count))
        download.cancel()

    @pyqtSlot('QNetworkReply')
    def fetch(self, reply):
        """Download a QNetworkReply to disk.

        Args:
            reply: The QNetworkReply to download.
        """
        _inline, suggested_filename = http.parse_content_disposition(reply)
        log.downloads.debug("fetch: {} -> {}".format(reply.url(),
                                                     suggested_filename))

        download = DownloadItem(reply, self)
        download.finished.connect(
            functools.partial(self.on_finished, download))
        download.data_changed.connect(
            functools.partial(self.on_data_changed, download))
        download.error.connect(self.on_error)
        download.basename = suggested_filename
        idx = len(self.downloads) + 1
        self.beginInsertRows(QModelIndex(), idx, idx)
        self.downloads.append(download)
        self.endInsertRows()

        q = usertypes.Question(self)
        q.text = "Save file to:"
        q.mode = usertypes.PromptMode.text
        q.default = suggested_filename
        q.answered.connect(download.set_filename)
        q.cancelled.connect(download.cancel)
        q.completed.connect(q.deleteLater)
        q.destroyed.connect(functools.partial(self.questions.remove, q))
        self.questions.append(q)
        download.cancelled.connect(q.abort)
        message_bridge = objreg.get('message-bridge', scope='window',
                                    window=self._win_id)
        message_bridge.ask(q, blocking=False)

    @pyqtSlot(DownloadItem)
    def on_finished(self, download):
        """Remove finished download."""
        log.downloads.debug("on_finished: {}".format(download))
        idx = self.downloads.index(download)
        self.beginRemoveRows(QModelIndex(), idx, idx)
        del self.downloads[idx]
        self.endRemoveRows()
        download.deleteLater()

    @pyqtSlot(DownloadItem)
    def on_data_changed(self, download):
        """Emit data_changed signal when download data changed."""
        idx = self.downloads.index(download)
        model_idx = self.index(idx, 0)
        qtutils.ensure_valid(model_idx)
        self.dataChanged.emit(model_idx, model_idx)

    @pyqtSlot(str)
    def on_error(self, msg):
        """Display error message on download errors."""
        message.error(self._win_id, "Download error: {}".format(msg))

    def last_index(self):
        """Get the last index in the model.

        Return:
            A (possibly invalid) QModelIndex.
        """
        idx = self.index(self.rowCount() - 1)
        return idx

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
            data = config.get('colors', 'downloads.fg')
        elif role == Qt.BackgroundRole:
            data = item.bg_color()
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

        The default would be Qt.ItemIsEnabled | Qt.ItemIsSelectable."""
        return Qt.ItemIsEnabled

    def rowCount(self, parent=QModelIndex()):
        """Get count of active downloads."""
        if parent.isValid():
            # We don't have children
            return 0
        return len(self.downloads)
