# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.


"""Code that is shared between the host blocker and Brave ad blocker."""

import os
import functools
from typing import IO, List, Optional

from PyQt5.QtCore import QUrl, QObject, pyqtSignal

from qutebrowser.api import downloads, message, config


class FakeDownload(downloads.TempDownload):

    """A download stub to use on_download_finished with local files."""

    def __init__(self, fileobj: IO[bytes]) -> None:
        # pylint: disable=super-init-not-called
        self.fileobj = fileobj
        self.successful = True


class BlocklistDownloads(QObject):
    """Download blocklists from the given URLs.

    Attributes:
        single_download_finished:
            A signal that is emitted when a single download has finished. The
            listening slot is provided with the download object.
        all_downloads_finished:
            A signal that is emitted when all downloads have finished. The
            first argument is the number of items downloaded.
        _urls: The URLs to download.
        _in_progress: The DownloadItems which are currently downloading.
        _done_count: How many files have been read successfully.
        _finished_registering_downloads:
            Used to make sure that if all the downloads finish really quickly,
            before all of the block-lists have been added to the download
            queue, we don't emit `single_download_finished`.
        _started: Has the `initiate` method been called?
        _finished: Has `all_downloads_finished` been emitted?
    """

    single_download_finished = pyqtSignal(object)  # arg: the file object
    all_downloads_finished = pyqtSignal(int)  # arg: download count

    def __init__(self, urls: List[QUrl], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._urls = urls

        self._in_progress: List[downloads.TempDownload] = []
        self._done_count = 0
        self._finished_registering_downloads = False
        self._started = False
        self._finished = False

    def initiate(self) -> None:
        """Initiate downloads of each url in `self._urls`."""
        if self._started:
            raise ValueError("This download has already been initiated")
        self._started = True

        if not self._urls:
            self._finished = True
            self.all_downloads_finished.emit(self._done_count)
            return

        for url in self._urls:
            self._download_blocklist_url(url)
        self._finished_registering_downloads = True

        if not self._in_progress and not self._finished:
            # The in-progress list is empty but we still haven't called the
            # completion callback yet. This happens when all downloads finish
            # before we've set `_finished_registering_dowloads` to False.
            self._finished = True
            self.all_downloads_finished.emit(self._done_count)

    def _download_blocklist_url(self, url: QUrl) -> None:
        """Take a blocklist url and queue it for download.

        Args:
            url: url to download
        """
        if url.scheme() == "file":
            # The URL describes a local file on disk if the url scheme is
            # "file://". We handle those as a special case.
            filename = url.toLocalFile()
            if os.path.isdir(filename):
                for entry in os.scandir(filename):
                    if entry.is_file():
                        self._import_local(entry.path)
            else:
                self._import_local(filename)
        else:
            download = downloads.download_temp(url)
            self._in_progress.append(download)
            download.finished.connect(
                functools.partial(self._on_download_finished, download)
            )

    def _import_local(self, filename: str) -> None:
        """Pretend that a local file was downloaded from the internet.

        Args:
            filename: path to a local file to import.
        """
        try:
            fileobj = open(filename, "rb")
        except OSError as e:
            message.error(
                "blockutils: Error while reading {}: {}".format(filename, e.strerror)
            )
            return
        download = FakeDownload(fileobj)
        self._in_progress.append(download)
        self._on_download_finished(download)

    def _on_download_finished(self, download: downloads.TempDownload) -> None:
        """Check if all downloads are finished and if so, trigger callback.

        Arguments:
            download: The finished download.
        """
        self._in_progress.remove(download)
        if download.successful:
            self._done_count += 1
            assert not isinstance(download.fileobj, downloads.UnsupportedAttribute)
            assert download.fileobj is not None
            try:
                # Call the user-provided callback
                self.single_download_finished.emit(download.fileobj)
            finally:
                download.fileobj.close()
        if not self._in_progress and self._finished_registering_downloads:
            self._finished = True
            self.all_downloads_finished.emit(self._done_count)


def is_whitelisted_url(url: QUrl) -> bool:
    """Check if the given URL is on the adblock whitelist."""
    whitelist = config.val.content.blocking.whitelist
    return any(pattern.matches(url) for pattern in whitelist)
