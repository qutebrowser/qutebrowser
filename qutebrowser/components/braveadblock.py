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

"""Functions related to the Brave adblocker."""

import io
import logging
import pathlib
import functools
import contextlib
import subprocess
from typing import Optional, IO, Iterator, List, Set

from PyQt5.QtCore import QUrl

from qutebrowser.api import (
    hook,
    config,
    message,
    interceptor,
    apitypes,
    qtutils,
)
from qutebrowser.api.interceptor import ResourceType
from qutebrowser.components.ublock_resources import (
    deserialize_resources_from_file,
    download_resources,
    EngineInfo,
)
from qutebrowser.components.utils import blockutils
from qutebrowser.components.utils.exceptions import DeserializationError
from qutebrowser.utils import version  # FIXME: Move needed parts into api namespace?

try:
    import adblock
except ImportError:
    adblock = None  # type: ignore[assignment]

logger = logging.getLogger("network")
ad_blocker: Optional["BraveAdBlocker"] = None


def _should_be_used() -> bool:
    """Whether the Brave adblocker should be used or not.

    Here we assume the adblock dependency is satisfied.
    """
    return config.val.content.blocking.method in ("auto", "both", "adblock")


def _possibly_show_missing_dependency_warning() -> None:
    """Show missing dependency warning, if appropriate.

    If the adblocking method is configured such that the Brave adblocker
    should be used, but the optional dependency is not satisfied, we show an
    error message.
    """
    adblock_info = version.MODULE_INFO["adblock"]

    method = config.val.content.blocking.method
    if method not in ("both", "adblock"):
        return

    if adblock_info.is_outdated():
        message.warning(
            f"Installed version {adblock_info.get_version()} of the 'adblock' "
            f"dependency is too old. Minimum supported is {adblock_info.min_version}."
        )
    elif not adblock_info.is_installed():
        message.warning(
            f"Ad blocking method is set to '{method}' but 'adblock' dependency is not "
            "installed."
        )
    else:
        message.warning(
            "The 'adblock' dependency was unavailable when qutebrowser was started, "
            "but now seems to be installed. Please :restart qutebrowser to use it."
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


def _resource_type_to_string(resource_type: Optional[ResourceType]) -> str:
    return _RESOURCE_TYPE_STRINGS.get(resource_type, "other")


@contextlib.contextmanager
def _map_exceptions() -> Iterator[None]:
    """Handle exception API differences in adblock 0.5.0.

    adblock < 0.5.0 will raise a ValueError with a string describing the
    exception class for all exceptions. With adblock 0.5.0+, it raises proper
    exception classes.

    This context manager unifies the two (only for DeserializationError so far).
    """
    adblock_deserialization_error = getattr(adblock, "DeserializationError", ValueError)

    try:
        yield
    except adblock_deserialization_error as e:
        if isinstance(e, ValueError) and str(e) != "DeserializationError":
            # All Rust exceptions get turned into a ValueError by
            # python-adblock
            raise
        raise DeserializationError(str(e))


class BraveAdBlocker:

    """Manage blocked hosts based on Brave's adblocker.

    Attributes:
        enabled: Whether to block ads or not.
        _has_basedir: Whether a custom --basedir is set.
        _cache_path: The path of the adblock engine cache file
        _engine: Brave ad-blocking engine.
    """

    def __init__(self, *, data_dir: pathlib.Path, has_basedir: bool = False) -> None:
        self.enabled = _should_be_used()
        self._has_basedir = has_basedir
        self._cache_path = data_dir / "adblock-cache.dat"
        self._resources_cache_path = data_dir / "adblock-resources-cache.dat"
        try:
            self._engine = adblock.Engine(adblock.FilterSet())
        except AttributeError:
            # this should never happen - let's get some infos if it does
            logger.debug(f"adblock module: {adblock}")
            dist = version.distribution()
            if (
                dist is not None
                and dist.parsed == version.Distribution.arch
                and hasattr(adblock, "__file__")
            ):
                proc = subprocess.run(
                    ["pacman", "-Qo", adblock.__file__],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                logger.debug(proc.stdout)
                logger.debug(proc.stderr)
            raise

    def _is_blocked(
        self,
        request_url: QUrl,
        first_party_url: Optional[QUrl] = None,
        resource_type: Optional[interceptor.ResourceType] = None,
    ) -> bool:
        """Check whether the given request is blocked."""
        if not self.enabled:
            # Do nothing if `content.blocking.method` is not set to enable the
            # use of this adblocking module.
            return False

        if (
            first_party_url is None
            or not first_party_url.isValid()
            or first_party_url.scheme() == "file"
        ):
            # FIXME: It seems that when `first_party_url` is None, every URL
            # I try is blocked. This may have been a result of me incorrectly
            # using the upstream library, or an upstream bug. For now we don't
            # block any request with `first_party_url=None`.
            return False

        qtutils.ensure_valid(request_url)

        if not config.get("content.blocking.enabled", url=first_party_url):
            # Do nothing if adblocking is disabled for this site.
            return False

        result = self._engine.check_network_urls(
            request_url.toString(),
            first_party_url.toString(),
            _resource_type_to_string(resource_type),
        )

        if not result.matched:
            return False
        elif result.exception is not None and not result.important:
            # Exception is not `None` when the blocker matched on an exception
            # rule. Effectively this means that there was a match, but the
            # request should not be blocked.
            #
            # An `important` match means that exceptions should not apply and
            # no further checking is necessary--the request should be blocked.
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

    def url_cosmetic_resources(
        self, url: QUrl
    ) -> Optional["adblock.UrlSpecificResources"]:
        """Returns the comsetic resources based on the filter rules."""
        if not self.enabled:
            # Do nothing if `content.blocking.method` is not set to enable the
            # use of this adblocking module.
            return None

        qtutils.ensure_valid(url)

        return self._engine.url_cosmetic_resources(url.toString())

    def hidden_class_id_selectors(
        self,
        classes: List[str],
        ids: List[str],
        exceptions: Set[str],
    ) -> Optional[List[str]]:
        """Returns the generic hidden class id selectors."""
        if not self.enabled:
            # Do nothing if `content.blocking.method` is not set to enable the
            # use of this adblocking module.
            return None

        return self._engine.hidden_class_id_selectors(classes, ids, exceptions)

    def read_cache(self) -> None:
        """Initialize the adblocking engine from cache file."""
        try:
            cache_exists = self._cache_path.is_file()
        except OSError:
            logger.error("Failed to read adblock cache", exc_info=True)
            return

        if cache_exists:
            logger.debug("Loading cached adblock data: %s", self._cache_path)
            try:
                with _map_exceptions():
                    self._engine.deserialize_from_file(str(self._cache_path))
            except DeserializationError:
                message.error(
                    "Reading adblock filter data failed (corrupted data?). "
                    "Please run :adblock-update."
                )
            except OSError as e:
                message.error(f"Reading adblock filter data failed: {e}")
        elif (
            config.val.content.blocking.adblock.lists
            and not self._has_basedir
            and config.val.content.blocking.enabled
            and self.enabled
        ):
            message.info("Run :adblock-update to get adblock lists.")

    def read_resources_cache(self) -> None:
        """Add resources to the adblocking engine from the resources cache file."""
        try:
            cache_exists = self._resources_cache_path.is_file()
        except OSError:
            logger.error("Failed to read adblock resources cache", exc_info=True)
            return

        if cache_exists:
            logger.debug(
                "Loading cached adblock resources data: %s", self._resources_cache_path
            )
            try:
                resources = deserialize_resources_from_file(self._resources_cache_path)
                for resource in resources:
                    self._engine.add_resource(
                        resource.name,
                        resource.aliases,
                        resource.content_type,
                        resource.content,
                    )
            except DeserializationError:
                message.error(
                    "Reading adblock resources data failed (corrupted data?). "
                    "Please run :adblock-update-resources."
                )
            except OSError as e:
                message.error(f"Reading adblock resources data failed: {e}")
        elif (
            not self._has_basedir
            and config.val.content.blocking.enabled
            and self.enabled
        ):
            message.info("Run :adblock-update-resources to get adblock resources.")

    def adblock_update(self) -> blockutils.BlocklistDownloads:
        """Update the adblock block lists."""
        logger.info("Downloading adblock filter lists...")

        filter_set = adblock.FilterSet()
        dl = blockutils.BlocklistDownloads(config.val.content.blocking.adblock.lists)
        dl.single_download_finished.connect(
            functools.partial(self._on_download_finished, filter_set=filter_set)
        )
        dl.all_downloads_finished.connect(
            functools.partial(self._on_lists_downloaded, filter_set=filter_set)
        )
        dl.initiate()
        return dl

    def _on_lists_downloaded(
        self, done_count: int, filter_set: "adblock.FilterSet"
    ) -> None:
        """Install block lists after files have been downloaded."""
        self._engine = adblock.Engine(filter_set)
        self._engine.serialize_to_file(str(self._cache_path))
        message.info(
            f"braveadblock: Filters successfully read from {done_count} sources."
        )

    def update_files(self) -> None:
        """Update files when the config changed."""
        if not config.val.content.blocking.adblock.lists:
            try:
                self._cache_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.exception("Failed to remove adblock cache file: %s", e)

    def _on_download_finished(
        self, url: QUrl, fileobj: IO[bytes], filter_set: "adblock.FilterSet"
    ) -> None:
        """When a blocklist download finishes, add it to the given filter set.

        Arguments:
            fileobj: The finished download's contents.
        """
        try:
            with io.TextIOWrapper(fileobj, encoding="utf-8") as text_io:
                filter_set.add_filter_list(text_io.read())
        except UnicodeDecodeError:
            message.info("braveadblock: Block list is not valid utf-8")

    def resources_update(self) -> blockutils.BlocklistDownloads:
        """Update ublock origin type resources."""
        return download_resources(
            EngineInfo(self._engine, self._cache_path, self._resources_cache_path)
        )


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


@hook.load_finished()
def add_cosmetic_filters(tab: apitypes.Tab, ok: bool) -> None:
    """After loading a page, inject javascript for relevant cosmetic filters."""
    if ad_blocker is None or not ok:
        return

    def to_js_code(cosmetic_resources: "adblock.UrlSpecificResources") -> str:
        css = (
            "\n".join(
                f"{sel} {{ display: none !important; }}"
                for sel in cosmetic_resources.hide_selectors
            )
            + "\n"
            + "\n".join(
                f"{sel} {{ {';'.join(styles)} }}"
                for sel, styles in cosmetic_resources.style_selectors.items()
            )
        )
        # Make sure things that could be confused as templates don't exist in the css
        assert "${" not in css and "`" not in css
        # There may be backslashes in the css. If so, we need to add another backslash
        # to escape them.
        css = css.replace("\\", "\\\\")
        js_code = (
            "const style = document.createElement('style');\n"
            f"style.textContent = `{css}`;\n"
            "document.head.append(style);\n"
            f"{cosmetic_resources.injected_script};\n"
        ) + (
            (
                """
                let classes = new Set();
                let ids = new Set();
                const walker = document.createTreeWalker(document.body);
                let node;
                while (node = walker.nextNode()) {
                    if (node.className) {
                        classes.add(node.className.toString());
                    }
                    if (node.id) {
                        ids.add(node.id.toString());
                    }
                }
                ({"classes": Array.from(classes), "ids": Array.from(ids)})
                """
            )
            if not cosmetic_resources.generichide
            else "true"
        )
        return f"{{ {js_code} }}"

    cosmetic_resources = ad_blocker.url_cosmetic_resources(tab.url())
    if cosmetic_resources is not None:

        def hidden_class_id_selectors_cb(data) -> None:
            logger.debug(
                f"hidden_class_id_selectors_cb called for {tab.url()} with {data}"
            )
            if data is None or type(data) != dict:
                return

            assert "classes" in data and "ids" in data

            selectors = ad_blocker.hidden_class_id_selectors(
                data["classes"], data["ids"], cosmetic_resources.exceptions
            )
            logger.debug(f"Number generic selectors: {len(selectors)}")

            css = "\n".join(
                f"{sel} {{ display: none !important; }}" for sel in selectors
            )
            if css:
                # Make sure things that could be confused as templates don't exist in
                # the css
                assert "${" not in css and "`" not in css
                # There may be backslashes in the css. If so, we need to add another
                # backslash to escape them.
                css = css.replace("\\", "\\\\")
                js_code = (
                    "const style = document.createElement('style');\n"
                    f"style.textContent = `{css}`;\n"
                    "document.head.append(style);\n"
                )
                js_code = f"{{ {js_code} }}"

                logger.debug(
                    f"js to inject for hidden class id selectors for {tab.url()}\n"
                    f"{js_code}"
                )
                tab.run_js_async(js_code)

        logger.debug(
            f"Returned cosmetic_resources for {tab.url()}: {cosmetic_resources}"
        )
        js_code = to_js_code(cosmetic_resources)
        logger.debug(
            f"js to inject for url-specific cosmetic filter for {tab.url()}:\n{js_code}"
        )
        # Call on world 0 to make sure injected javascript interacts with main page
        tab.run_js_async(js_code, callback=hidden_class_id_selectors_cb, world=0)


@hook.init()
def init(context: apitypes.InitContext) -> None:
    """Initialize the Brave ad blocker."""
    global ad_blocker

    adblock_info = version.MODULE_INFO["adblock"]
    if not adblock_info.is_usable():
        # We want 'adblock' to be an optional dependency. If the module is
        # not installed or is outdated, we simply keep the `ad_blocker` global at
        # `None`.
        _possibly_show_missing_dependency_warning()
        return

    ad_blocker = BraveAdBlocker(
        data_dir=context.data_dir, has_basedir=context.args.basedir is not None
    )
    ad_blocker.read_cache()
    interceptor.register(ad_blocker.filter_request)
