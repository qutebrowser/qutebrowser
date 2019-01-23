# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Functions related to ad blocking."""

import io
import os.path
import functools
import posixpath
import zipfile
import logging
import typing
import pathlib

from PyQt5.QtCore import QUrl

from _adblock import AdBlock
from qutebrowser.api import (cmdutils, hook, config, message, downloads,
                             interceptor, apitypes)


logger = logging.getLogger('misc')
_brave_adblocker = typing.cast('BraveAdBlocker', None)


class BraveAdBlocker:

    """Manage blocked hosts based from /etc/hosts-like files.

    Attributes:
        _in_progress: The DownloadItems which are currently downloading.
        _done_count: How many files have been read successfully.
        _has_basedir: Whether a custom --basedir is set.
    """

    def __init__(self, *, data_dir: pathlib.Path, config_dir: pathlib.Path,
                 has_basedir: bool = False) -> None:
        self._has_basedir = has_basedir
        self._in_progress = []  # type: typing.List[downloads.TempDownload]
        self._done_count = 0
        self._local_adblock_cache = str(data_dir / 'adblock-cache.dat')
        self._adblock = AdBlock()

    def _is_blocked(self, request_url: QUrl,
                    first_party_url: QUrl = None) -> bool:
        """Check whether the given request is blocked."""
        if not config.get('content.brave_adblock.enabled', False):
            return False
        if first_party_url is not None and not first_party_url.isValid():
            return False
        url_s = request_url.toString()
        fp_host = first_party_url.host()
        if fp_host and self._adblock.matches(url_s, fp_host):
            return True
        return False

    def filter_request(self, info: interceptor.Request) -> None:
        """Block the given request if necessary."""
        if self._is_blocked(request_url=info.request_url,
                            first_party_url=info.first_party_url):
            logger.info(
                "Request to {} blocked by brave adblocker.".format(
                    info.request_url.toString()))
            info.block()

    def read_cache(self) -> None:
        """Read hosts from the existing blocked-hosts file."""

        if not os.path.isfile(self._local_adblock_cache):
            if (config.val.content.brave_adblock.lists and
                    not self._has_basedir and
                    config.val.content.brave_adblock.enabled):
                message.info("Run :brave-adblock-update to get adblock lists.")
        else:
            logging.info("loading adblock cached data: %s", self._local_adblock_cache)
            self._adblock.load(self._local_adblock_cache)

    def adblock_update(self) -> None:
        """Update the adblock block lists."""
        self._done_count = 0
        logging.info("Downloading new blocklists.")
        for url in config.val.content.brave_adblock.lists:
            logging.info("Adding: %s" % url.toString())
            download = downloads.download_temp(url)
            self._in_progress.append(download)
            download.finished.connect(
                functools.partial(self._on_download_finished, download))

    def _on_lists_downloaded(self) -> None:
        """Install adblock lists after files have been downloaded."""
        message.info("brave adblock: Saving cache file.")
        self._adblock.save(self._local_adblock_cache)

    def update_files(self) -> None:
        """Update files when the config changed."""
        if not config.val.content.brave_adblock.lists:
            try:
                os.remove(self._local_adblock_cache)
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.exception("Failed to delete adblock cache file: {}".format(e))

    def _on_download_finished(self, download: downloads.TempDownload) -> None:
        """Check if all downloads are finished and if so, trigger reading.

        Arguments:
            download: The finished download.
        """
        self._in_progress.remove(download)
        if download.successful:
            self._done_count += 1
            try:
                download.fileobj.seek(0)
                text = io.TextIOWrapper(download.fileobj)
                self._adblock.parse(text.read())
                text.close()
            finally:
                download.fileobj.close()
        if not self._in_progress:
            try:
                self._on_lists_downloaded()
            except OSError:
                logger.exception("Failed to write brave adblock cache!")


@cmdutils.register()
def brave_adblock_update() -> None:
    """Update the adblock block lists.

    This updates `~/.local/share/qutebrowser/blocked-hosts` with downloaded
    host lists and re-reads `~/.config/qutebrowser/blocked-hosts`.
    """
    # FIXME: As soon as we can register instances again, we should move this
    # back to the class.
    _brave_adblocker.adblock_update()


@hook.config_changed('content.brave_adblock.lists')
def on_config_changed() -> None:
    _brave_adblocker.update_files()


@hook.init()
def init(context: apitypes.InitContext) -> None:
    """Initialize the brave adblocker."""
    global _brave_adblocker
    _brave_adblocker = BraveAdBlocker(
        data_dir=context.data_dir,
        config_dir=context.config_dir,
        has_basedir=context.args.basedir is not None)
    _brave_adblocker.read_cache()
    interceptor.register(_brave_adblocker.filter_request)
