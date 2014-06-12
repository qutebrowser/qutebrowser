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

import os.path

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject, QTimer

import qutebrowser.config.config as config
import qutebrowser.utils.message as message
from qutebrowser.utils.log import downloads as logger
from qutebrowser.utils.usertypes import PromptMode


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
        _last_done: The count of bytes which where downloaded when calculating
                    the speed the last time.
        _last_percentage: The remembered percentage for percentage_changed.

    Signals:
        speed_changed: The download speed changed.
                       arg: The speed in bytes/s
        percentage_changed: The download percentage changed.
                            arg: The new percentage, -1 if unknown.
        finished: The download was finished.
    """

    REFRESH_INTERVAL = 200
    speed_changed = pyqtSignal(float)
    percentage_changed = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, reply, filename, parent=None):
        """Constructor.

        Args:
            reply: The QNetworkReply to download.
            filename: The full filename to save the download to.
        """
        super().__init__(parent)
        self.reply = reply
        self.bytes_done = None
        self.bytes_total = None
        self.speed = None
        self._last_done = None
        self._last_percentage = None
        # FIXME exceptions
        self.fileobj = open(filename, 'wb')
        reply.downloadProgress.connect(self.on_download_progress)
        reply.finished.connect(self.on_finished)
        reply.finished.connect(self.finished)
        reply.error.connect(self.on_error)
        reply.readyRead.connect(self.on_ready_read)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_speed)
        self.timer.setInterval(self.REFRESH_INTERVAL)
        self.timer.start()

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

    @pyqtSlot(int, int)
    def on_download_progress(self, bytes_done, bytes_total):
        """Upload local variables when the download progress changed.

        Args:
            bytes_done: How many bytes are downloaded.
            bytes_total: How many bytes there are to download in total.
        """
        self.bytes_done = bytes_done
        self.bytes_total = bytes_total
        perc = round(self.percentage)
        if perc != self._last_percentage:
            logger.debug("{}% downloaded".format(perc))
            self.percentage_changed.emit(perc)
            self._last_percentage = perc

    @pyqtSlot()
    def on_finished(self):
        """Clean up when the download was finished."""
        self.bytes_done = self.bytes_total
        self.timer.stop()
        self.fileobj.write(self.reply.readAll())
        self.fileobj.close()
        self.reply.close()
        self.reply.deleteLater()
        logger.debug("Download finished")

    @pyqtSlot()
    def on_ready_read(self):
        """Read available data and save file when ready to read."""
        # FIXME exceptions
        self.fileobj.write(self.reply.readAll())

    @pyqtSlot()
    def update_speed(self):
        """Recalculate the current download speed."""
        if self._last_done is None:
            delta = self.bytes_done
        else:
            delta = self.bytes_done - self._last_done
        self.speed = delta * 1000 / self.REFRESH_INTERVAL
        logger.debug("Download speed: {} bytes/sec".format(self.speed))
        self._last_done = self.bytes_done
        self.speed_changed.emit(self.speed)

    @pyqtSlot(int)
    def on_error(self, code):
        logger.debug("Error {} in download".format(code))


class DownloadManager(QObject):

    """Manager for running downloads.

    Signals:
        download_about_to_be_added: A new download will be added.
                                    arg: The index of the new download.
        download_added: A new download was added.
        download_about_to_be_finished: A download will be finished and removed.
                                       arg: The index of the new download.
        download_finished: A download was finished and removed.
    """

    download_about_to_be_added = pyqtSignal(int)
    download_added = pyqtSignal()
    download_about_to_be_finished = pyqtSignal(int)
    download_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloads = []

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
        suggested_filename = os.path.join(download_location,
                                          suggested_filename)
        logger.debug("fetch: {} -> {}".format(reply.url(), suggested_filename))
        filename = message.modular_question("Save file to:", PromptMode.text,
                                            suggested_filename)
        if filename is not None:
            download = DownloadItem(reply, filename)
            download.finished.connect(self.on_finished)
            self.download_about_to_be_added.emit(len(self.downloads) + 1)
            self.downloads.append(download)
            self.download_added.emit()

    @pyqtSlot()
    def on_finished(self):
        idx = self.downloads.index(self.sender())
        self.download_about_to_be_finished.emit(idx)
        del self.downloads[idx]
        self.download_finished.emit()
