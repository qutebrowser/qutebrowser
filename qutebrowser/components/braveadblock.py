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

"""Functions related to the Brave adblocker."""

import io
import logging
import typing
import pathlib

from PyQt5.QtCore import QUrl

from qutebrowser.api import (
    hook,
    config,
    message,
    downloads,
    interceptor,
    apitypes,
    qtutils,
)
from qutebrowser.api.interceptor import ResourceType
from qutebrowser.components.utils import blockutils

try:
    import adblock
except ImportError:
    adblock = None  # type: ignore[assignment]


logger = logging.getLogger("network")
ad_blocker = typing.cast(typing.Optional["BraveAdBlocker"], None)


def _should_be_used() -> bool:
    """Whether the Brave adblocker should be used or not.

    Here we assume the adblock dependency is satisfied.
    """
    method = config.val.content.blocking.method
    return method in ("auto", "both", "adblock")


def _possibly_show_missing_dependency_warning() -> None:
    """Show missing dependency warning, if appropriate.

    If the adblocking method is configured such that the Brave adblocker
    should be used, but the optional dependency is not satisfied, we show an
    error message.
    """
    method = config.val.content.blocking.method
    if method in ("adblock", "both"):
        message.warning(
            "Ad blocking method is set to '{}' but 'adblock' dependency is"
            " not installed.".format(method)
        )


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


class BraveAdBlocker:

    """Manage blocked hosts based on Brave's adblocker.

    Attributes:
        enabled: Should we block ads or not
        _has_basedir: Whether a custom --basedir is set.
        _cache_path: The path of the adblock engine cache file
        _in_progress: The DownloadItems which are currently downloading.
        _done_count: How many files have been read successfully.
        _finished_registering_downloads:
            Used to make sure that if all the downloads finish really quickly,
            before all of the block-lists have been added to the download
            queue, we don't call `_on_lists_downloaded`.
        _wip_filter_set:
            If we're in midst of updating the block lists, this attribute
            contains a "work-in-progress" filter set that will later be used to
            create a new instance of `_engine`. Otherwise it's `None`.
        _engine: Brave ad-blocking engine.
    """

    def __init__(self, *, data_dir: pathlib.Path, has_basedir: bool = False) -> None:
        self.enabled = _should_be_used()
        self._has_basedir = has_basedir
        self._cache_path = data_dir / "adblock-cache.dat"
        self._in_progress = []  # type: typing.List[downloads.TempDownload]
        self._done_count = 0
        self._finished_registering_downloads = False
        self._wip_filter_set = None  # type: typing.Optional[adblock.FilterSet]
        self._engine = adblock.Engine(adblock.FilterSet())

    def _is_blocked(
        self,
        request_url: QUrl,
        first_party_url: typing.Optional[QUrl] = None,
        resource_type: typing.Optional[interceptor.ResourceType] = None,
    ) -> bool:
        """Check whether the given request is blocked."""
        if not self.enabled:
            return False

        if first_party_url is not None and not first_party_url.isValid():
            first_party_url = None

        if not first_party_url:
            return False

        qtutils.ensure_valid(request_url)

        if not config.get("content.blocking.enabled", url=first_party_url):
            # Do nothing if adblocking is disabled.
            return False

        result = self._engine.check_network_urls(
            request_url.toString(),
            first_party_url.toString(),
            resource_type_to_string(resource_type),
        )

        if not result.matched:
            return False
        elif result.exception is not None and not result.important:
            logger.debug(
                "Excepting %s from being blocked by %s because of %s",
                request_url.toDisplayString(),
                result.filter,
                result.exception,
            )
            return False
        elif blockutils.is_whitelisted_url(request_url):
            logger.debug(
                "Request to %s is whitelisted, thus not blocked",
                request_url.toDisplayString(),
            )
            return False
        return True

    def filter_request(self, info: interceptor.Request) -> None:
        """Block the given request if necessary."""
        if self._is_blocked(info.request_url, info.first_party_url, info.resource_type):
            logger.debug(
                "Request to %s blocked by ad blocker.",
                info.request_url.toDisplayString(),
            )
            info.block()

    def read_cache(self) -> None:
        """Initialize the adblocking engine from cache file."""
        if self._cache_path.is_file():
            logger.debug("Loading cached adblock data: %s", self._cache_path)
            self._engine.deserialize_from_file(str(self._cache_path))
        else:
            if (
                config.val.content.blocking.adblock.lists
                and not self._has_basedir
                and config.val.content.blocking.enabled
                and self.enabled
            ):
                message.info("Run :adblock-update to get adblock lists.")

    def adblock_update(self) -> None:
        """Update the adblock block lists."""
        self._done_count = 0
        self._wip_filter_set = adblock.FilterSet()
        logger.info("Downloading adblock filter lists...")

        blocklists = config.val.content.blocking.adblock.lists
        if not blocklists:
            # Blocklists are None or length zero
            self._on_lists_downloaded()
        else:
            self._finished_registering_downloads = False
            for url in blocklists:
                blockutils.download_blocklist_url(
                    url, self._on_download_finished, self._in_progress
                )
            self._finished_registering_downloads = True
            if not self._in_progress and self._wip_filter_set is not None:
                self._on_lists_downloaded()

    def _on_lists_downloaded(self) -> None:
        """Install block lists after files have been downloaded."""
        assert self._wip_filter_set is not None
        self._engine = adblock.Engine(self._wip_filter_set)
        self._wip_filter_set = None
        self._engine.serialize_to_file(str(self._cache_path))
        logger.info(
            "adblock: Filters successfully read from {} sources".format(
                self._done_count
            )
        )

    def update_files(self) -> None:
        """Update files when the config changed."""
        if not config.val.content.blocking.adblock.lists:
            try:
                self._cache_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.exception("Failed to remove adblock cache file: {}".format(e))

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
            assert self._wip_filter_set is not None
            try:
                download.fileobj.seek(0)
                # WORKAROUND for https://github.com/python/typeshed/pull/4145
                fileobj = typing.cast(typing.BinaryIO, download.fileobj)
                text = io.TextIOWrapper(fileobj, encoding="utf-8")
                self._wip_filter_set.add_filter_list(text.read())
                text.close()
            except UnicodeDecodeError:
                message.info("Block list is not valid utf-8")
            finally:
                download.fileobj.close()
        if len(self._in_progress) == 0 and self._finished_registering_downloads:
            try:
                self._on_lists_downloaded()
            except OSError:
                logger.exception("Failed to write host block list!")


@hook.config_changed("content.blocking.adblock.lists")
def on_lists_changed() -> None:
    """Remove cached blocker from disk when blocklist changes."""
    if ad_blocker is not None:
        ad_blocker.update_files()


@hook.config_changed("content.blocking.method")
def on_method_changed() -> None:
    """When the adblocking method changes, update blocker accordingly."""
    if ad_blocker is not None:
        # This implies the 'adblock' dependency is satisfied
        ad_blocker.enabled = _should_be_used()
    else:
        _possibly_show_missing_dependency_warning()


@hook.init()
def init(context: apitypes.InitContext) -> None:
    """Initialize the Brave ad blocker."""
    global ad_blocker

    if adblock is None:
        # We want 'adblock' to be an optional dependency. If the module is
        # not found, we simply set the `ad_blocker` global to `None`. Always
        # remember to check the case where `ad_blocker` is `None`!
        ad_blocker = None  # type: ignore[unreachable]
        _possibly_show_missing_dependency_warning()
        return

    ad_blocker = BraveAdBlocker(
        data_dir=context.data_dir, has_basedir=context.args.basedir is not None
    )
    ad_blocker.read_cache()
    interceptor.register(ad_blocker.filter_request)
