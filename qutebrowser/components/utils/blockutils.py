# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Code that is shared between the host blocker and Brave ad blocker."""

import typing
import os
import functools

from PyQt5.QtCore import QUrl

from qutebrowser.api import downloads, message


class FakeDownload(downloads.TempDownload):

    """A download stub to use on_download_finished with local files."""

    def __init__(
        self, fileobj: typing.IO[bytes]
    ) -> None:
        # pylint: disable=super-init-not-called
        self.fileobj = fileobj
        self.successful = True


def download_blocklist_url(
    url: QUrl,
    on_download_finished: typing.Callable[[downloads.TempDownload], None],
    in_progress: typing.List[downloads.TempDownload],
) -> None:
    """Take a blocklist url and queue it for download.

    Args:
        url: url to download
        on_download_finished: function to be called when downloads are finished
        in_progress: list to append in-progress downloads to
    """
    if url.scheme() == "file":
        # The URL describes a local file on disk if the url scheme is
        # "file://". We handle those as a special case.
        filename = url.toLocalFile()
        if os.path.isdir(filename):
            for entry in os.scandir(filename):
                if entry.is_file():
                    _import_local(entry.path, on_download_finished, in_progress)
        else:
            _import_local(filename, on_download_finished, in_progress)
    else:
        download = downloads.download_temp(url)
        in_progress.append(download)
        download.finished.connect(functools.partial(on_download_finished, download))


def _import_local(
    filename: str,
    on_download_finished: typing.Callable[[downloads.TempDownload], None],
    in_progress: typing.List[downloads.TempDownload],
) -> None:
    """Adds the contents of a file to the blocklist.

    Args:
        filename: path to a local file to import.
        on_download_finished: function to be called when downloads are finished
        in_progress: list to append in-progress downloads to
    """
    try:
        fileobj = open(filename, "rb")
    except OSError as e:
        message.error(
            "blockutils: Error while reading {}: {}".format(filename, e.strerror)
        )
        return
    download = FakeDownload(fileobj)
    in_progress.append(download)
    on_download_finished(download)
