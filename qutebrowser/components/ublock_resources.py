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

"""Functions related to the ublock origin resources for the Brave adblocker."""

import base64
import dataclasses
import functools
import json
import logging
import io
import pathlib
import re
from typing import Optional, IO, List, Dict

from qutebrowser.qt.core import QUrl
from qutebrowser.api import (
    message,
)
from qutebrowser.components.utils import blockutils
from qutebrowser.components.utils.exceptions import DeserializationError

try:
    import adblock
except ImportError:
    adblock = None  # type: ignore[assignment]

logger = logging.getLogger("network")


@dataclasses.dataclass
class Resource:
    """Class for keeping track of resource information for adblock."""

    name: str
    aliases: List[str]
    content_type: str
    content: str


class EngineInfo:
    """Keeps track of engine object and cache paths.

    Attributes:
        engine: The engine object.
        cache_path: The cache path for the overall engine.
        resources_cache_path: The resources cache path for the engine.
    """

    def __init__(
        self,
        engine: "adblock.Engine",
        cache_path: pathlib.Path,
        resources_cache_path: pathlib.Path,
    ):
        self.engine = engine
        self.cache_path = cache_path
        self.resources_cache_path = resources_cache_path


_REDIRECT_RESOURCES_URL = QUrl(
    "https://github.com/gorhill/uBlock/raw/master/src/js/redirect-resources.js"
)

_SCRIPTLETS_URL = QUrl(
    "https://raw.githubusercontent.com/gorhill/uBlock/master/assets/resources/scriptlets.js"
)

_WEB_ACCESSIBLE_RESOURCES_URL_TEMPLATE = (
    "https://github.com/gorhill/uBlock/raw/master/src/web_accessible_resources/{}"
)


def deserialize_resources_from_file(path: pathlib.Path) -> List[Resource]:
    """Deserialize and return resource information from cached resources data file."""
    with open(path, encoding="utf-8") as f:
        try:
            # TODO: In the future, we may want to use a serialization library (such as
            # pyserde) instead of doing this manually like this
            resources = json.load(f)
            return [
                Resource(d["name"], d["aliases"], d["content_type"], d["content"])
                for d in resources
            ]
        except (TypeError, KeyError):
            raise DeserializationError(f"Failed to deserialize {path}")


def _serialize_resources_to_file(resources: List[Resource], path: pathlib.Path) -> None:
    """Serialize resource information to cached resources data file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump([dataclasses.asdict(resource) for resource in resources], f)


def _parse_resource(
    aliases_map: Dict[str, List[str]],
    url: QUrl,
    fileobj: IO[bytes],
) -> Resource:
    ext_map = {
        ".gif": "image/gif",
        ".html": "text/html",
        ".js": "application/javascript",
        ".mp3": "audio/mp3",
        ".mp4": "video/mp4",
        ".png": "image/png",
        ".txt": "text/plain",
        ".css": "text/css",
        ".xml": "application/octet-stream",
        "": "application/octet-stream",
    }

    ext = pathlib.Path(url.path()).suffix

    if ext not in ext_map:
        raise ValueError(f"Don't know this extension: {ext}")

    if ext_map[ext] in (
        "application/javascript",
        "text/html",
        "text/plain",
        "text/css",
    ):
        with io.TextIOWrapper(fileobj, encoding="utf-8") as text_io:
            content = text_io.read().replace("\r", "").encode()
    else:
        content = fileobj.read()

    return Resource(
        pathlib.Path(url.path()).name,
        aliases_map[url.toString()],
        ext_map[ext],
        base64.b64encode(content).decode("utf-8"),
    )


_TOP_COMMENT_RE = r"^/\*[\S\s]+?\n\*/\s*"
_NON_EMPTY_LINE_RE = r"\S"


def _parse_scriptlets(
    fileobj: IO[bytes],
) -> List[Resource]:
    with io.TextIOWrapper(fileobj, encoding="utf-8") as text_io:
        lines = re.sub(_TOP_COMMENT_RE, "", text_io.read()).split("\n")

    resources: List[Resource] = []
    current_resource = None
    for line in lines:
        if line.startswith("#") or line.startswith("// ") or line == "//":
            continue

        if current_resource is None:
            if line.startswith("/// "):
                name = line[4:].strip()
                current_resource = Resource(name, [], "", "")
            continue

        if line.startswith("/// "):  # type: ignore[unreachable]
            tokens = line[4:].split()
            if len(tokens) >= 2 and tokens[0] == "alias":
                current_resource.aliases.append(tokens[1])
            continue

        if re.search(_NON_EMPTY_LINE_RE, line):
            current_resource.content += line.rstrip() + "\n"
            continue

        if "{{1}}" in current_resource.content:
            current_resource.content_type = "template"
        else:
            current_resource.content_type = "application/javascript"

        current_resource.content = base64.b64encode(
            current_resource.content.encode()
        ).decode("utf-8")

        resources.append(current_resource)
        current_resource = None

    return resources


def _on_resource_download(
    resources: List[Resource],
    aliases_map: Dict[str, List[str]],
    url: QUrl,
    fileobj: IO[bytes],
) -> None:
    """On downloading a resource, parse it and add append it to the resources list.

    If the url is the scriptlets url, then parse that differently.
    """
    try:
        if url == _SCRIPTLETS_URL:
            resources.extend(_parse_scriptlets(fileobj))
        else:
            resources.append(_parse_resource(aliases_map, url, fileobj))
    except UnicodeDecodeError:
        message.info(f"braveadblock: Resource from {url} is not valid utf-8")
    except ValueError:
        message.info(f"braveadblock: Could not parse resource from {url}")


def _on_all_resources_downloaded(
    resources: List[Resource],
    engine_info: EngineInfo,
    done_count: int,
) -> None:
    """After downloading all resources, create the cache and update the engine."""
    _serialize_resources_to_file(resources, engine_info.resources_cache_path)
    for resource in resources:
        if adblock.__version__ >= "0.6.0":
            engine_info.engine.add_resource(
                resource.name,
                resource.content_type,
                resource.content,
                resource.aliases,
            )
        else:
            engine_info.engine.add_resource(
                resource.name, resource.content_type, resource.content
            )
    engine_info.engine.serialize_to_file(str(engine_info.cache_path))
    message.info(
        f"braveadblock: Successfully updated engine with {done_count} resources."
    )


_REDIRECTABLE_RESOURCES_DECL = "export default new Map(["
_MAP_END_RE = r"^\s*\]\s*\)"


def _on_redirect_engine_download(  # noqa: C901
    _url: QUrl, fileobj: IO[bytes], engine_info: EngineInfo
) -> Optional[blockutils.BlocklistDownloads]:
    """Download redirect-resources.js, parse it, and get the list of resource urls.

    To parse it, we take the portion that refers to the map, and turn it into JSON, and
    decode with json.load. The inspiration for this code comes from
    https://github.com/brave/adblock-rust/blob/master/src/resources/resource_assembler.rs

    Since this is almost a one-to-one mapping of the code in the above file, it's
    probably to keep everything in one function (hence the noqa: C901).
    """
    try:
        # Extract the lines for the map
        map_lines = []
        map_opening_seen = False
        with io.TextIOWrapper(fileobj, encoding="utf-8") as text_io:
            for line in text_io.readlines():
                if not map_opening_seen:
                    if _REDIRECTABLE_RESOURCES_DECL in line:
                        map_opening_seen = True
                        map_lines.append("[")
                elif re.search(_MAP_END_RE, line):
                    map_lines.append("]")
                    break
                else:
                    map_lines.append(line)

                if map_lines:
                    comment_idx = map_lines[-1].find("//")
                    if comment_idx >= 0:
                        map_lines[-1] = map_lines[-1][:comment_idx]

        # Get rid of trailing block comments
        map_lines = [re.sub(r"/\*[^'\"]*\*/\s*$", "", line) for line in map_lines]

        # Get rid of all whitespace
        map_str = re.sub(r"\s+", "", "".join(map_lines))

        # Replace all ' with "
        map_str = map_str.replace("'", '"')

        # Get rid of all trailing commas
        map_str = re.sub(r",([\],\}])", r"\1", map_str)

        # Replace all property keys directly preceded by a `{` or a `,` and followed by
        # a `:` with double-quoted versions.
        map_str = re.sub(r"([\{,])([a-zA-Z][a-zA-Z0-9_]*):", r'\1"\2":', map_str)

        # Read via json
        resources_map = json.loads(map_str)

        resource_urls: List[QUrl] = []
        # Mapping from resource url (in string form) to list of aliases
        aliases_map: Dict[str, List[str]] = {}
        for resource in resources_map:
            name, data = resource
            # Skip any resource with params since we don't know how to deal with it
            if "params" in data:
                continue

            url_str = _WEB_ACCESSIBLE_RESOURCES_URL_TEMPLATE.format(name)
            if "alias" in data:
                if isinstance(data["alias"], list):
                    aliases_map[url_str] = data["alias"]
                else:
                    aliases_map[url_str] = [data["alias"]]
            else:
                aliases_map[url_str] = []

            resource_urls.append(QUrl(url_str))

        resources: List[Resource] = []
        dl = blockutils.BlocklistDownloads(resource_urls + [_SCRIPTLETS_URL])
        dl.single_download_finished.connect(
            functools.partial(_on_resource_download, resources, aliases_map)
        )
        dl.all_downloads_finished.connect(
            functools.partial(
                _on_all_resources_downloaded,
                resources,
                engine_info,
            )
        )
        dl.initiate()

        return dl

    except UnicodeDecodeError:
        message.error("braveadblock: redirect-resources.js is not in valid utf-8")
    except (TypeError, json.JSONDecodeError):
        message.error("braveadblock: redirect-resources.js could not be parsed")

    return None


def download_resources(engine_info: EngineInfo) -> blockutils.BlocklistDownloads:
    """Download ublock origin type resources and add them to given engine.

    Also updates the engine's cache path and resources cache path while we're at it.
    """
    dl = blockutils.BlocklistDownloads([_REDIRECT_RESOURCES_URL])
    dl.single_download_finished.connect(
        functools.partial(_on_redirect_engine_download, engine_info=engine_info)
    )
    dl.initiate()
    return dl
