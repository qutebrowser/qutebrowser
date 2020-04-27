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
import logging
import typing
import pathlib

from PyQt5.QtCore import QUrl

from qutebrowser.api import (
    cmdutils,
    hook,
    config,
    message,
    downloads,
    interceptor,
    apitypes,
    qtutils,
)
from qutebrowser.api.interceptor import ResourceType


logger = logging.getLogger("misc")
_ad_blocker = typing.cast(typing.Optional['BraveAdBlocker'], None)


def _is_whitelisted_url(url: QUrl) -> bool:
    """Check if the given URL is on the adblock whitelist."""
    for pattern in config.val.content.ad_blocking.whitelist:
        if pattern.matches(url):
            return True

    # Prevent a block-list for being able to block itself, otherwise you
    # couldn't update it.
    if config.val.content.ad_blocking.lists is not None:
        # FIXME: This list comprehension is probably too expensive to do for
        # every request. There must be a better way.
        block_list_urls = [
            url.toString() for url in config.val.content.ad_blocking.lists
        ]
        if url.toString() in block_list_urls:
            return True

    return False


def resource_type_to_string(resource_type: ResourceType) -> str:
    MAP = {
        ResourceType.main_frame: "main_frame",
        ResourceType.sub_frame: "sub_frame",
        ResourceType.stylesheet: "stylesheet",
        ResourceType.script: "script",
        ResourceType.image: "image",
        ResourceType.font_resource: "font",
        ResourceType.sub_resource: "sub_frame",
        ResourceType.object: "object",
        ResourceType.media: "media",
        ResourceType.worker: "other",
        ResourceType.shared_worker: "other",
        ResourceType.prefetch: "other",
        ResourceType.favicon: "image",
        ResourceType.xhr: "xhr",
        ResourceType.ping: "ping",
        ResourceType.service_worker: "other",
        ResourceType.csp_report: "csp_report",
        ResourceType.plugin_resource: "other",
        ResourceType.preload_main_frame: "other",
        ResourceType.preload_sub_frame: "other",
        ResourceType.unknown: "other",
    }
    return MAP.get(resource_type, "other")


# TODO: Move this code somewhere so that `adblock.py` can make use of it too.
class _FakeDownload(downloads.TempDownload):

    """A download stub to use on_download_finished with local files."""

    def __init__(
        self, fileobj: typing.IO[bytes]  # pylint: disable=super-init-not-called
    ) -> None:
        self.fileobj = fileobj
        self.successful = True


class BraveAdBlocker:

    """Manage blocked hosts based from /etc/hosts-like files.

    Attributes:
        _in_progress: The DownloadItems which are currently downloading.
        _done_count: How many files have been read successfully.
        _has_basedir: Whether a custom --basedir is set.
        _cache_path: The path of the adblock engine cache file
        _engine: Brave ad-blocking engine.
    """

    def __init__(
        self,
        *,
        # FIXME: This type should be `adblock.Engine`. I don't know how to
        # annotate it in such a way that mypy doesn't complain about it being
        # undefined, since `adblock` is an optional dependency:
        # ```
        # qutebrowser/components/braveadblock.py:125: error: Name 'adblock' is not defined  [name-defined]
        #    engine: "adblock.Engine",
        # ```
        engine: typing.Any,
        data_dir: pathlib.Path,
        has_basedir: bool = False
    ) -> None:
        self._has_basedir = has_basedir
        self._in_progress = []  # type: typing.List[downloads.TempDownload]
        self._done_count = 0
        self._cache_path = str(data_dir / "adblock-cache.dat")
        self._engine = engine

    def _is_blocked(
        self,
        request_url: QUrl,
        first_party_url: typing.Optional[QUrl] = None,
        resource_type: typing.Optional[interceptor.ResourceType] = None,
    ) -> bool:
        """Check whether the given request is blocked."""
        first_party_url = first_party_url
        if first_party_url is not None and not first_party_url.isValid():
            first_party_url = None

        qtutils.ensure_valid(request_url)

        if not config.get("content.ad_blocking.enabled", url=first_party_url):
            # Do nothing if adblocking is disabled.
            return False

        result = self._engine.check_network_urls(
            request_url.toString(),
            first_party_url.toString() if first_party_url else "",
            resource_type_to_string(resource_type) if resource_type else "",
        )

        if not result.matched:
            return False
        if (result.exception is not None) and (result.important is None):
            logger.debug(
                "Excepting {} from being blocked by {} because of {}".format(
                    request_url.toString(), result.filter, result.exception
                )
            )
            return False
        if _is_whitelisted_url(request_url):
            logger.debug(
                "Request to {} is whitelisted, thus not blocked".format(
                    request_url.toString()
                )
            )
            return False
        return True

    def filter_request(self, info: interceptor.Request) -> None:
        """Block the given request if necessary."""
        if self._is_blocked(info.request_url, info.first_party_url, info.resource_type):
            logger.info(
                "Request to {} blocked by ad blocker.".format(
                    info.request_url.toString()
                )
            )
            info.block()

    def read_cache(self) -> None:
        if os.path.isfile(self._cache_path):
            logger.info("Loading cached adblock data: {}".format(self._cache_path))
            self._engine.deserialize_from_file(self._cache_path)
        else:
            if (
                config.val.content.ad_blocking.lists
                and not self._has_basedir
                and config.val.content.ad_blocking.enabled
            ):
                message.info("Run :brave-adblock-update to get adblock lists.")

    def adblock_update(self) -> None:
        """Update the adblock block lists."""
        self._done_count = 0
        logger.info("Downloading adblock filter lists...")
        for url in config.val.content.ad_blocking.lists:
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
        """Adds the contents of a file to the blocklist.

        Args:
            filename: path to a local file to import.
        """
        try:
            fileobj = open(filename, "rb")
        except OSError as e:
            message.error(
                "adblock: Error while reading {}: {}".format(filename, e.strerror)
            )
            return
        download = _FakeDownload(fileobj)
        self._in_progress.append(download)
        self._on_download_finished(download)

    def _on_lists_downloaded(self) -> None:
        """Install block lists after files have been downloaded."""
        self._engine.serialize_to_file(self._cache_path)
        logger.info("Block lists have been successfully imported")

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
            assert not isinstance(download.fileobj, downloads.UnsupportedAttribute)
            assert download.fileobj is not None
            try:
                download.fileobj.seek(0)
                text = io.TextIOWrapper(download.fileobj, encoding="utf-8")
                self._engine.add_filter_list(text.read())
                text.close()
            except UnicodeDecodeError:
                message.info("Block list is not valid utf-8")
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

    if _ad_blocker is not None:
        _ad_blocker.adblock_update()
    else:
        message.warning(
            "The 'adblock' dependency is not installed. Please install it to continue."
        )


@hook.config_changed("content.ad_blocking.lists")
def on_config_changed() -> None:
    if _ad_blocker is not None:
        _ad_blocker.update_files()


@hook.init()
def init(context: apitypes.InitContext) -> None:
    """Initialize the Brave ad blocker."""
    global _ad_blocker

    try:
        import adblock
    except ImportError:
        # We want 'adblock' to be an optional dependency. If the module is
        # not found, we simply set the `_ad_blocker` global to `None`. Always
        # remember to check the case where `_ad_blocker` is `None`!
        _ad_blocker = None
        return

    engine = adblock.Engine([])
    _ad_blocker = BraveAdBlocker(
        engine=engine,
        data_dir=context.data_dir,
        has_basedir=context.args.basedir is not None,
    )
    _ad_blocker.read_cache()
    interceptor.register(_ad_blocker.filter_request)
