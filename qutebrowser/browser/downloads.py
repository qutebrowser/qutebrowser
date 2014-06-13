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

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject, QTimer
from PyQt5.QtNetwork import QNetworkReply

import qutebrowser.config.config as config
import qutebrowser.utils.message as message
from qutebrowser.utils.log import downloads as logger
from qutebrowser.utils.usertypes import PromptMode, Question
from qutebrowser.utils.misc import (interpolate_color, format_seconds,
                                    format_size)


class DownloadItem(QObject):

    """A single download currently running.

    Class attributes:
        REFRESH_INTERVAL: How often to refresh the speed, in msec.

    Attributes:
        reply: The QNetworkReply associated with this download.
        percentage: How many percent were downloaded successfully.
        bytes_done: How many bytes there are already downloaded.
        bytes_total: The total count of bytes.
        speed: The current download speed, in bytes per second.
        fileobj: The file object to download the file to.
        filename: The filename of the download.
        is_cancelled: Whether the download was cancelled.
        _last_done: The count of bytes which where downloaded when calculating
                    the speed the last time.
        _last_percentage: The remembered percentage for data_changed.

    Signals:
        data_changed: The downloads metadata changed.
        finished: The download was finished.
        cancelled: The download was cancelled.
        error: An error with the download occured.
               arg: The error message as string.
    """

    REFRESH_INTERVAL = 200
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
        self.reply = reply
        self.bytes_done = None
        self.bytes_total = None
        self.speed = None
        self.basename = '???'
        self.fileobj = None
        self.filename = None
        self.is_cancelled = False
        self._do_delayed_write = False
        self._last_done = None
        self._last_percentage = None
        reply.setReadBufferSize(16 * 1024 * 1024)
        reply.downloadProgress.connect(self.on_download_progress)
        reply.finished.connect(self.on_reply_finished)
        reply.error.connect(self.on_reply_error)
        reply.readyRead.connect(self.on_ready_read)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_speed)
        self.timer.setInterval(self.REFRESH_INTERVAL)
        self.timer.start()

    def __str__(self):
        """Get the download as a string.

        Example: foo.pdf [699.2kB/s|0.34|16%|4.253/25.124]
        """
        perc = 0 if self.percentage is None else round(self.percentage)
        remaining = (format_seconds(self.remaining_time)
                     if self.remaining_time is not None else '?')
        speed = format_size(self.speed, suffix='B/s')
        down = format_size(self.bytes_done, suffix='B')
        total = format_size(self.bytes_total, suffix='B')
        return ('{name} [{speed:>10}|{remaining:>5}|{perc:>2}%|'
                '{down}/{total}]'.format(name=self.basename, speed=speed,
                                         remaining=remaining, perc=perc,
                                         down=down, total=total))

    def _die(self, msg):
        """Abort the download and emit an error."""
        self.error.emit(msg)
        self.reply.abort()
        self.reply.deleteLater()
        if self.fileobj is not None:
            try:
                self.fileobj.close()
            except OSError as e:
                self.error.emit(e.strerror)
        self.finished.emit()

    @property
    def percentage(self):
        """Property to get the current download percentage."""
        if self.bytes_total == -1:
            return -1
        elif self.bytes_total == 0:
            return 0
        elif self.bytes_done is None or self.bytes_total is None:
            return None
        else:
            return 100 * self.bytes_done / self.bytes_total

    @property
    def remaining_time(self):
        """Property to get the remaining download time in seconds."""
        if (self.bytes_total is None or self.bytes_total <= 0 or
                self.speed is None or self.speed == 0):
            return None
        return (self.bytes_total - self.bytes_done) / self.speed

    def bg_color(self):
        """Background color to be shown."""
        start = config.get('colors', 'downloads.bg.start')
        stop = config.get('colors', 'downloads.bg.stop')
        system = config.get('colors', 'downloads.bg.system')
        if self.percentage is None:
            return start
        else:
            return interpolate_color(start, stop, self.percentage, system)

    def cancel(self):
        """Cancel the download."""
        logger.debug("cancelled")
        self.cancelled.emit()
        self.is_cancelled = True
        self.reply.abort()
        self.reply.deleteLater()
        if self.fileobj is not None:
            self.fileobj.close()
        if self.filename is not None:
            os.remove(self.filename)
        self.finished.emit()


    def set_filename(self, filename):
        """Set the filename to save the download to.

        Args:
            filename: The full filename to save the download to.
                      None: special value to stop the download.
        """
        if self.filename is not None:
            raise ValueError("Filename was already set! filename: {}, "
                             "existing: {}".format(filename, self.filename))
        self.filename = filename
        self.basename = os.path.basename(filename)
        try:
            self.fileobj = open(filename, 'wb')
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
        logger.debug("Doing delayed write...")
        self._do_delayed_write = False
        self.fileobj.write(self.reply.readAll())
        self.fileobj.close()
        self.reply.close()
        self.reply.deleteLater()
        self.finished.emit()
        logger.debug("Download finished")

    @pyqtSlot(int, int)
    def on_download_progress(self, bytes_done, bytes_total):
        """Upload local variables when the download progress changed.

        Args:
            bytes_done: How many bytes are downloaded.
            bytes_total: How many bytes there are to download in total.
        """
        self.bytes_done = bytes_done
        self.bytes_total = bytes_total
        self.data_changed.emit()

    @pyqtSlot()
    def on_reply_finished(self):
        """Clean up when the download was finished.

        Note when this gets called, only the QNetworkReply has finished. This
        doesn't mean the download (i.e. writing data to the disk) is finished
        as well. Therefore, we can't close() the QNetworkReply in here yet.
        """
        self.bytes_done = self.bytes_total
        self.timer.stop()
        if self.is_cancelled:
            return
        logger.debug("Reply finished, fileobj {}".format(self.fileobj))
        if self.fileobj is None:
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
        if self.fileobj is None:
            # No filename has been set yet, so we don't empty the buffer.
            return
        try:
            self.fileobj.write(self.reply.readAll())
        except OSError as e:
            self._die(e.strerror)

    @pyqtSlot(int)
    def on_reply_error(self, code):
        """Handle QNetworkReply errors."""
        if code == QNetworkReply.OperationCanceledError:
            return
        else:
            self.error.emit(self.reply.errorString())

    @pyqtSlot()
    def update_speed(self):
        """Recalculate the current download speed."""
        if self._last_done is None:
            if self.bytes_done is None:
                self.speed = 0
            else:
                delta = self.bytes_done
                self.speed = delta * 1000 / self.REFRESH_INTERVAL
        else:
            delta = self.bytes_done - self._last_done
            self.speed = delta * 1000 / self.REFRESH_INTERVAL
        logger.debug("Download speed: {} bytes/sec".format(self.speed))
        self._last_done = self.bytes_done
        self.data_changed.emit()


class DownloadManager(QObject):

    """Manager for running downloads.

    Attributes:
        downloads: A list of active DownloadItems.
        questions: A list of Question objects to not GC them.

    Signals:
        download_about_to_be_added: A new download will be added.
                                    arg: The index of the new download.
        download_added: A new download was added.
        download_about_to_be_finished: A download will be finished and removed.
                                       arg: The index of the new download.
        download_finished: A download was finished and removed.
        data_changed: The data to be displayed in a model changed.
                      arg: The index of the download which changed.
    """

    download_about_to_be_added = pyqtSignal(int)
    download_added = pyqtSignal()
    download_about_to_be_finished = pyqtSignal(int)
    download_finished = pyqtSignal()
    data_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloads = []
        self.questions = []

    def _get_filename(self, reply):
        """Get a suitable filename to download a file to.

        Args:
            reply: The QNetworkReply to get a filename for.
        """
        filename = None
        # First check if the Content-Disposition header has a filename
        # attribute.
        if reply.hasRawHeader('Content-Disposition'):
            header = reply.rawHeader('Content-Disposition')
            data = header.split(':', maxsplit=1)[1].strip()
            for pair in data.split(';'):
                if '=' in pair:
                    key, value = pair.split('=')
                    if key == 'filename':
                        filename = value.strip('"')
                        break
        # Then try to get filename from url
        if not filename:
            filename = reply.url().path()
        # If that fails as well, use a fallback
        if not filename:
            filename = 'qutebrowser-download'
        return os.path.basename(filename)

    @pyqtSlot('QNetworkReply')
    def fetch(self, reply):
        """Download a QNetworkReply to disk.

        Args:
            reply: The QNetworkReply to download.
        """
        suggested_filename = self._get_filename(reply)
        download_location = config.get('storage', 'download-directory')
        suggested_filepath = os.path.join(download_location,
                                          suggested_filename)
        logger.debug("fetch: {} -> {}".format(reply.url(), suggested_filepath))
        download = DownloadItem(reply)
        download.finished.connect(self.on_finished)
        download.data_changed.connect(self.on_data_changed)
        download.error.connect(self.on_error)
        download.basename = suggested_filename
        self.download_about_to_be_added.emit(len(self.downloads) + 1)
        self.downloads.append(download)
        self.download_added.emit()

        q = Question()
        q.text = "Save file to:"
        q.mode = PromptMode.text
        q.default = suggested_filepath
        q.answered.connect(download.set_filename)
        q.cancelled.connect(download.cancel)
        self.questions.append(q)
        download.cancelled.connect(q.abort)
        message.instance().question.emit(q, False)

    @pyqtSlot()
    def on_finished(self):
        """Remove finished download."""
        logger.debug("on_finished: {}".format(self.sender()))
        idx = self.downloads.index(self.sender())
        self.download_about_to_be_finished.emit(idx)
        del self.downloads[idx]
        self.download_finished.emit()

    @pyqtSlot()
    def on_data_changed(self):
        """Emit data_changed signal when download data changed."""
        idx = self.downloads.index(self.sender())
        self.data_changed.emit(idx)

    @pyqtSlot(str)
    def on_error(self, msg):
        """Display error message on download errors."""
        message.error("Download error: {}".format(msg), queue=True)
