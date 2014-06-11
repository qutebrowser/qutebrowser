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

from PyQt5.QtCore import pyqtSlot, QObject

from qutebrowser.utils.log import downloads as logger


class DownloadItem(QObject):

    """A single download currently running.

    Attributes:
        reply: The QNetworkReply associated with this download.
        percentage: How many percent were downloaded successfully.
    """

    def __init__(self, reply, parent=None):
        super().__init__(parent)
        self.reply = reply
        self.percentage = None

    @pyqtSlot(int, int)
    def on_download_progress(self, done, total):
        if total == -1:
            perc = -1
        else:
            perc = 100 * done / total
        logger.debug("{}% done".format(perc))
        self.percentage = perc


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
        filename = self._get_filename(reply)
        logger.debug("fetch: {} -> {}".format(reply.url(), filename))
        reply.downloadProgress.connect(self.on_download_progress)
        reply.readyRead.connect(self.on_ready_read)
        reply.finished.connect(self.on_finished)

    @pyqtSlot(int, int)
    def on_download_progress(self, done, total):
        if total == -1:
            perc = '???'
        else:
            perc = 100 * done / total
        logger.debug("{}% done".format(perc))

    @pyqtSlot()
    def on_ready_read(self):
        logger.debug("readyread")
        self.sender().readAll()

    @pyqtSlot()
    def on_finished(self):
        logger.debug("finished")
