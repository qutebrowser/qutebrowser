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

if typing.TYPE_CHECKING:
    import adblock


logger = logging.getLogger("network")
_ad_blocker = typing.cast(typing.Optional["BraveAdBlocker"], None)


def _is_whitelisted_url(url: QUrl) -> bool:
    """Check if the given URL is on the adblock whitelist."""
    for pattern in config.val.content.blocking.whitelist:
        if pattern.matches(url):
            return True

    # Prevent a block-list from being able to block itself, otherwise you
    # couldn't update it.
    blocklists = (
        config.val.content.blocking.adblock.lists
        + config.val.content.blocking.hosts.lists
    )
    if blocklists is not None:
        if url in blocklists:
            return True

    return False


_RESOURCE_TYPE_STRINGS = {
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
    None: "",
}


def resource_type_to_string(resource_type: typing.Optional[ResourceType]) -> str:
    return _RESOURCE_TYPE_STRINGS.get(resource_type, "other")


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
        _engine_factory: A function that can be called to create an empty
                         adblocking engine.
        _engine: Brave ad-blocking engine.
    """

    def __init__(
        self,
        *,
        engine_factory: typing.Callable[[], "adblock.Engine"],
        data_dir: pathlib.Path,
        has_basedir: bool = False
    ) -> None:
        self._has_basedir = has_basedir
        self._in_progress = []  # type: typing.List[downloads.TempDownload]
        self._done_count = 0
        self._cache_path = data_dir / "adblock-cache.dat"
        self._engine_factory = engine_factory
        self._engine = engine_factory()

    def _is_blocked(
        self,
        request_url: QUrl,
        first_party_url: typing.Optional[QUrl] = None,
        resource_type: typing.Optional[interceptor.ResourceType] = None,
    ) -> bool:
        """Check whether the given request is blocked."""
        if first_party_url is not None and not first_party_url.isValid():
            first_party_url = None

        if not first_party_url:
            return False

        qtutils.ensure_valid(request_url)

        if not config.get("content.blocking.adblock.enabled", url=first_party_url):
            # Do nothing if adblocking is disabled.
            return False

        result = self._engine.check_network_urls(
            request_url.toString(),
            first_party_url.toString(),
            resource_type_to_string(resource_type),
        )

        if not result.matched:
            return False
        if result.exception is not None and result.important is None:
            logger.debug(
                "Excepting {} from being blocked by {} because of {}".format(
                    request_url.toDisplayString(), result.filter, result.exception
                )
            )
            return False
        if _is_whitelisted_url(request_url):
            logger.debug(
                "Request to {} is whitelisted, thus not blocked".format(
                    request_url.toDisplayString()
                )
            )
            return False
        return True

    def filter_request(self, info: interceptor.Request) -> None:
        """Block the given request if necessary."""
        if self._is_blocked(info.request_url, info.first_party_url, info.resource_type):
            logger.debug(
                "Request to {} blocked by ad blocker.".format(
                    info.request_url.toDisplayString()
                )
            )
            info.block()

    def read_cache(self) -> None:
        if self._cache_path.is_file():
            logger.debug("Loading cached adblock data: {}".format(self._cache_path))
            self._engine.deserialize_from_file(str(self._cache_path))
        else:
            if (
                config.val.content.blocking.adblock.lists
                and not self._has_basedir
                and config.val.content.blocking.adblock.enabled
            ):
                message.info("Run :brave-adblock-update to get adblock lists.")

    def adblock_update(self) -> None:
        """Update the adblock block lists."""
        self._done_count = 0
        self._engine = self._engine_factory()
        logger.info("Downloading adblock filter lists...")
        for url in config.val.content.blocking.adblock.lists:
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
        self._engine.serialize_to_file(str(self._cache_path))
        logger.info("Block lists have been successfully imported")

    def update_files(self) -> None:
        """Update files when the config changed."""
        if not config.val.content.blocking.adblock.lists:
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
    """Update the adblock block lists."""

    if _ad_blocker is not None:
        _ad_blocker.adblock_update()
    else:
        message.warning(
            "The 'adblock' dependency is not installed. Please install it to continue."
        )


@hook.config_changed("content.blocking.adblock.lists")
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

    _ad_blocker = BraveAdBlocker(
        engine_factory=lambda: adblock.Engine([]),
        data_dir=context.data_dir,
        has_basedir=context.args.basedir is not None,
    )
    _ad_blocker.read_cache()
    interceptor.register(_ad_blocker.filter_request)
