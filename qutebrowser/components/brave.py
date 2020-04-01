# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import adblock

from qutebrowser.api import (cmdutils, hook, config, message, downloads,
                             interceptor, apitypes, qtutils)


logger = logging.getLogger('misc')
_host_blocker = typing.cast('HostBlocker', None)


class BraveAdBlocker:

    """Manage blocked hosts based from /etc/hosts-like files.

    Attributes:
        _in_progress: The DownloadItems which are currently downloading.
        _done_count: How many files have been read successfully.
        _has_basedir: Whether a custom --basedir is set.
        _engine: Brave ad-blocking engine.
    """

    def __init__(self, *, data_dir: pathlib.Path, config_dir: pathlib.Path,
                 has_basedir: bool = False) -> None:
        self._has_basedir = has_basedir
        self._in_progress = []  # type: typing.List[downloads.TempDownload]
        self._done_count = 0
        self._cache_path = str(data_dir / "adblock-cache.dat")
        self._engine = adblock.Engine([])


    def filter_request(self, info: interceptor.Request) -> None:
        """Block or redirect the given request if necessary."""
        request_type = info.resource_type.name if info.resource_type else ""

        first_party_url = info.first_party_url
        if first_party_url is not None and not first_party_url.isValid():
            first_party_url = None

        qtutils.ensure_valid(info.request_url)

        if not config.get('content.ad_blocking.enabled',
                          url=first_party_url):
            # Do nothing if adblocking is disabled.
            return

        result = self._engine.check_network_urls(
            info.request_url.toString(),
            first_party_url.toString() if first_party_url else "",
            info.resource_type.name if info.resource_type else "",
        )
        if result.redirect is not None:
            logger.info("Request to {} redirected to {} by ad blocker."
            .format(info.request_url.toString(), result.redirect))
            info.redirect(QUrl(result.redirect))
        elif result.matched:
            logger.info("Request to {} blocked by ad blocker."
                .format(info.request_url.toString()))
            info.block()

    def read_cache(self) -> None:
        if os.path.isfile(self._cache_path):
            logger.info("Loading cached adblock data: {}".format(self._cache_path))
            self._engine.deserialize_from_file(self._cache_path)
        else:
            if (config.val.content.ad_blocking.lists and
                    not self._has_basedir and
                    config.val.content.ad_blocking.enabled):
                message.info("Run :brave-adblock-update to get adblock lists.")

    def adblock_update(self) -> None:
        """Update the adblock block lists."""
        self._done_count = 0
        logger.info("Downloading adblock filter lists...")
        for url in config.val.content.ad_blocking.lists:
            download = downloads.download_temp(url)
            self._in_progress.append(download)
            download.finished.connect(
                functools.partial(self._on_download_finished, download))

    def _on_lists_downloaded(self) -> None:
        """Install block lists after files have been downloaded."""
        self._engine.serialize_to_file(self._cache_path)

    def update_files(self) -> None:
        """Update files when the config changed."""
        if not config.val.content.ad_blocking.lists:
            try:
                os.remove(self._cache_path)
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.exception("Failed to adblock cache file: {}".format(e))


    def _on_download_finished(self, download: downloads.TempDownload) -> None:
        """Check if all downloads are finished and if so, trigger reading.

        Arguments:
            download: The finished download.
        """
        self._in_progress.remove(download)
        if download.successful:
            self._done_count += 1
            assert not isinstance(download.fileobj,
                                  downloads.UnsupportedAttribute)
            assert download.fileobj is not None
            try:
                download.fileobj.seek(0)
                text = io.TextIOWrapper(download.fileobj)
                self._engine.add_filter_list(text.read())
                text.close()
            finally:
                download.fileobj.close()
        if not self._in_progress:
            try:
                self._on_lists_downloaded()
            except OSError:
                logger.exception("Failed to write host block list!")


@cmdutils.register()
def brave_adblock_update() -> None:
    """Update the adblock block lists.

    This updates `~/.local/share/qutebrowser/blocked-hosts` with downloaded
    host lists and re-reads `~/.config/qutebrowser/blocked-hosts`.
    """
    # FIXME: As soon as we can register instances again, we should move this
    # back to the class.
    _ad_blocker.adblock_update()


@hook.config_changed('content.ad_blocking.lists')
def on_config_changed() -> None:
    _ad_blocker.update_files()


@hook.init()
def init(context: apitypes.InitContext) -> None:
    """Initialize the Brave ad blocker."""
    global _ad_blocker
    _ad_blocker = BraveAdBlocker(data_dir=context.data_dir,
                                config_dir=context.config_dir,
                                has_basedir=context.args.basedir is not None)
    _ad_blocker.read_cache()
    interceptor.register(_ad_blocker.filter_request)
