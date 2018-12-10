# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


import io

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl

from qutebrowser.browser import downloads, qtnetworkdownloads
from qutebrowser.utils import objreg


class TempDownload(QObject):

    """A download of some data into a file object."""

    finished = pyqtSignal()

    def __init__(self, item: qtnetworkdownloads.DownloadItem) -> None:
        self._item = item
        self._item.finished.connect(self._on_download_finished)
        self.successful = False
        self.fileobj = item.fileobj

    @pyqtSlot()
    def _on_download_finished(self) -> None:
        self.successful = self._item.successful
        self.finished.emit()


def download_temp(url: QUrl) -> TempDownload:
    """Download the given URL into a file object.

    The download is not saved to disk.
    """
    fobj = io.BytesIO()
    fobj.name = 'temporary: ' + url.host()
    target = downloads.FileObjDownloadTarget(fobj)
    download_manager = objreg.get('qtnetwork-download-manager')
    return download_manager.get(url, target=target, auto_remove=True)
