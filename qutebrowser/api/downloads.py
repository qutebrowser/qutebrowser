# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""APIs related to downloading files."""


import io

from qutebrowser.qt.core import QObject, pyqtSignal, pyqtSlot, QUrl

from qutebrowser.browser import downloads, qtnetworkdownloads
from qutebrowser.utils import objreg


UnsupportedAttribute = downloads.UnsupportedAttribute


class TempDownload(QObject):

    """A download of some data into a file object."""

    finished = pyqtSignal()

    def __init__(self, item: qtnetworkdownloads.DownloadItem) -> None:
        super().__init__()
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

    Returns a ``TempDownload`` object, which triggers a ``finished`` signal
    when the download has finished::

        dl = downloads.download_temp(QUrl("https://www.example.com/"))
        dl.finished.connect(functools.partial(on_download_finished, dl))

    After the download has finished, its ``successful`` attribute can be
    checked to make sure it finished successfully. If so, its contents can be
    read by accessing the ``fileobj`` attribute::

        def on_download_finished(download: downloads.TempDownload) -> None:
            if download.successful:
                print(download.fileobj.read())
                download.fileobj.close()
    """
    fobj = io.BytesIO()
    fobj.name = 'temporary: ' + url.host()
    target = downloads.FileObjDownloadTarget(fobj)
    download_manager = objreg.get('qtnetwork-download-manager')
    # cache=False is set as a WORKAROUND for MS Defender thinking we're a trojan
    # downloader when caching the hostblock list...
    return download_manager.get(url, target=target, auto_remove=True, cache=False)
