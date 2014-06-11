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
    """

    REFRESH_INTERVAL = 1000

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
        # FIXME exceptions
        self.fileobj = open(filename, 'wb')
        reply.downloadProgress.connect(self.on_download_progress)
        reply.finished.connect(self.on_finished)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_speed)
        self.timer.setInterval(self.REFRESH_INTERVAL)
        self.timer.start()

    @property
    def percentage(self):
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
        self.bytes_done = bytes_done
        self.bytes_total = bytes_total

    @pyqtSlot()
    def on_finished(self):
        """Clean up when the download was finished."""
        self.bytes_done = self.bytes_total
        self.timer.stop()
        self.fileobj.write(self.reply.readAll())
        self.fileobj.close()
        self.reply.close()
        self.reply.deleteLater()

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
        self.speed = delta / self.REFRESH_INTERVAL / 1000
        logger.debug("Download speed: {} bytes/sec".format(self.speed))
        self._last_done = self.bytes_done


class DownloadManager(QObject):

    """Manager for running downloads."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloads = []

    def _get_filename(self, reply):
        """Get a suitable filename to download a file to.

        Args:
            reply: The QNetworkReply to get a filename for."""
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
            self.downloads.append(DownloadItem(reply, filename))
