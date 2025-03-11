# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Chromium .pak repacking.

This entire file is a great WORKAROUND for https://bugreports.qt.io/browse/QTBUG-118157
and the fact we can't just simply disable the hangouts extension:
https://bugreports.qt.io/browse/QTBUG-118452

It's yet another big hack. If you think this is bad, look at elf.py instead.

The name of this file might or might not be inspired by a certain vegetable,
as well as the "joy" this bug has caused me.

Useful references:

- https://sweetscape.com/010editor/repository/files/PAK.bt (010 editor <3)
- https://textslashplain.com/2022/05/03/chromium-internals-pak-files/
- https://github.com/myfreeer/chrome-pak-customizer
- https://source.chromium.org/chromium/chromium/src/+/main:tools/grit/pak_util.py
- https://source.chromium.org/chromium/chromium/src/+/main:tools/grit/grit/format/data_pack.py

This is a "best effort" parser. If it errors out, we don't apply the workaround
instead of crashing.
"""

import os
import shutil
import pathlib
import dataclasses
import contextlib
from typing import ClassVar, IO, Optional
from collections.abc import Iterator

from qutebrowser.config import config
from qutebrowser.misc import binparsing, objects
from qutebrowser.utils import qtutils, standarddir, version, utils, log, message

HANGOUTS_MARKER = b"// Extension ID: nkeimhogjdpnpccoofpliimaahmaaome"
HANGOUTS_IDS = [
    # Linux
    47222,  # QtWebEngine 6.9 Beta 3
    43932,  # QtWebEngine 6.9 Beta 1
    43722,  # QtWebEngine 6.8
    41262,  # QtWebEngine 6.7
    36197,  # QtWebEngine 6.6
    34897,  # QtWebEngine 6.5
    32707,  # QtWebEngine 6.4
    27537,  # QtWebEngine 6.3
    23607,  # QtWebEngine 6.2

    248,  # macOS
    381,  # Windows
]
PAK_VERSION = 5
RESOURCES_ENV_VAR = "QTWEBENGINE_RESOURCES_PATH"
DISABLE_ENV_VAR = "QUTE_DISABLE_PAKJOY"
CACHE_DIR_NAME = "webengine_resources_pak_quirk"
PAK_FILENAME = "qtwebengine_resources.pak"

TARGET_URL = b"https://*.google.com/*"
REPLACEMENT_URL = b"https://qute.invalid/*"
assert len(TARGET_URL) == len(REPLACEMENT_URL)


@dataclasses.dataclass
class PakHeader:

    """Chromium .pak header (version 5)."""

    encoding: int  # uint32
    resource_count: int  # uint16
    _alias_count: int  # uint16

    _FORMAT: ClassVar[str] = "<IHH"

    @classmethod
    def parse(cls, fobj: IO[bytes]) -> "PakHeader":
        """Parse a PAK version 5 header from a file."""
        return cls(*binparsing.unpack(cls._FORMAT, fobj))


@dataclasses.dataclass
class PakEntry:

    """Entry description in a .pak file."""

    resource_id: int  # uint16
    file_offset: int  # uint32
    size: int = 0  # not in file

    _FORMAT: ClassVar[str] = "<HI"

    @classmethod
    def parse(cls, fobj: IO[bytes]) -> "PakEntry":
        """Parse a PAK entry from a file."""
        return cls(*binparsing.unpack(cls._FORMAT, fobj))


class PakParser:
    """Parse webengine pak and find patch location to disable Google Meet extension."""

    def __init__(self, fobj: IO[bytes]) -> None:
        """Parse the .pak file from the given file object."""
        pak_version = binparsing.unpack("<I", fobj)[0]
        if pak_version != PAK_VERSION:
            raise binparsing.ParseError(f"Unsupported .pak version {pak_version}")

        self.fobj = fobj
        entries = self._read_header()
        self.manifest_entry, self.manifest = self._find_manifest(entries)

    def find_patch_offset(self) -> int:
        """Return byte offset of TARGET_URL into the pak file."""
        try:
            return self.manifest_entry.file_offset + self.manifest.index(TARGET_URL)
        except ValueError:
            raise binparsing.ParseError("Couldn't find URL in manifest")

    def _maybe_get_hangouts_manifest(self, entry: PakEntry) -> Optional[bytes]:
        self.fobj.seek(entry.file_offset)
        data = self.fobj.read(entry.size)

        if not data.startswith(b"{") or not data.rstrip(b"\n").endswith(b"}"):
            # not JSON
            return None

        if HANGOUTS_MARKER not in data:
            return None

        return data

    def _read_header(self) -> dict[int, PakEntry]:
        """Read the header and entry index from the .pak file."""
        entries = []

        header = PakHeader.parse(self.fobj)
        for _ in range(header.resource_count + 1):  # + 1 due to sentinel at end
            entries.append(PakEntry.parse(self.fobj))

        for entry, next_entry in zip(entries, entries[1:]):
            if entry.resource_id == 0:
                raise binparsing.ParseError("Unexpected sentinel entry")
            entry.size = next_entry.file_offset - entry.file_offset

        if entries[-1].resource_id != 0:
            raise binparsing.ParseError("Missing sentinel entry")
        del entries[-1]

        return {entry.resource_id: entry for entry in entries}

    def _find_manifest(self, entries: dict[int, PakEntry]) -> tuple[PakEntry, bytes]:
        to_check = list(entries.values())
        for hangouts_id in HANGOUTS_IDS:
            if hangouts_id in entries:
                # Most likely candidate, based on previous known ID
                to_check.insert(0, entries[hangouts_id])

        for entry in to_check:
            manifest = self._maybe_get_hangouts_manifest(entry)
            if manifest is not None:
                return entry, manifest

        raise binparsing.ParseError("Couldn't find hangouts manifest")


def _find_webengine_resources() -> pathlib.Path:
    """Find the QtWebEngine resources dir.

    Mirrors logic from QtWebEngine:
    https://github.com/qt/qtwebengine/blob/v6.6.0/src/core/web_engine_library_info.cpp#L293-L341
    """
    if RESOURCES_ENV_VAR in os.environ:
        return pathlib.Path(os.environ[RESOURCES_ENV_VAR])

    candidates = []
    qt_data_path = qtutils.library_path(qtutils.LibraryPath.data)
    if utils.is_mac:  # pragma: no cover
        # I'm not sure how to arrive at this path without hardcoding it
        # ourselves. importlib.resources.files("PyQt6.Qt6") can serve as a
        # replacement for the qtutils bit but it doesn't seem to help find the
        # actual Resources folder.
        candidates.append(
            qt_data_path / "lib" / "QtWebEngineCore.framework" / "Resources"
        )

    candidates += [
        qt_data_path / "resources",
        qt_data_path,
        pathlib.Path(objects.qapp.applicationDirPath()),
        pathlib.Path.home() / f".{objects.qapp.applicationName()}",
    ]

    for candidate in candidates:
        if (candidate / PAK_FILENAME).exists():
            return candidate

    candidates_str = "\n".join(f"    {p}" for p in candidates)
    raise FileNotFoundError(
        f"Couldn't find webengine resources dir, candidates:\n{candidates_str}")


def copy_webengine_resources() -> Optional[pathlib.Path]:
    """Copy qtwebengine resources to local dir for patching."""
    resources_dir = _find_webengine_resources()
    work_dir = pathlib.Path(standarddir.cache()) / CACHE_DIR_NAME

    if work_dir.exists():
        log.misc.debug(f"Removing existing {work_dir}")
        shutil.rmtree(work_dir)

    versions = version.qtwebengine_versions(avoid_init=True)
    if not (
        # https://bugreports.qt.io/browse/QTBUG-118157
        versions.webengine == utils.VersionNumber(6, 6)
        # https://bugreports.qt.io/browse/QTBUG-113369
        or (
            versions.webengine >= utils.VersionNumber(6, 5)
            and versions.webengine < utils.VersionNumber(6, 5, 3)
            and config.val.colors.webpage.darkmode.enabled
        )
        # https://github.com/qutebrowser/qutebrowser/issues/8257
        or config.val.qt.workarounds.disable_hangouts_extension
    ):
        # No patching needed
        return None

    log.misc.debug(
        "Copying webengine resources for quirk patching: "
        f"{resources_dir} -> {work_dir}"
    )

    shutil.copytree(resources_dir, work_dir)
    return work_dir


def _patch(file_to_patch: pathlib.Path) -> None:
    """Apply any patches to the given pak file."""
    if not file_to_patch.exists():
        _error(
            None,
            "Resource pak doesn't exist at expected location! "
            f"Not applying quirks. Expected location: {file_to_patch}"
        )
        return

    with open(file_to_patch, "r+b") as f:
        try:
            parser = PakParser(f)
            log.misc.debug(f"Patching pak entry: {parser.manifest_entry}")
            offset = parser.find_patch_offset()
            binparsing.safe_seek(f, offset)
            f.write(REPLACEMENT_URL)
        except binparsing.ParseError as e:
            _error(e, "Failed to apply quirk to resources pak.")


def _error(exc: Optional[BaseException], text: str) -> None:
    if config.val.qt.workarounds.disable_hangouts_extension:
        # Explicitly requested -> hard error
        lines = ["Failed to disable Hangouts extension:", text]
        if exc is None:
            lines.append(str(exc))
        message.error("\n".join(lines))
    elif exc is None:
        # Best effort -> just log
        log.misc.error(text)
    else:
        log.misc.exception(text)


@contextlib.contextmanager
def patch_webengine() -> Iterator[None]:
    """Apply any patches to webengine resource pak files."""
    if os.environ.get(DISABLE_ENV_VAR):
        log.misc.debug(f"Not applying quirk due to {DISABLE_ENV_VAR}")
        yield
        return

    try:
        # Still calling this on Qt != 6.6 so that the directory is cleaned up
        # when not needed anymore.
        webengine_resources_path = copy_webengine_resources()
    except OSError as e:
        _error(e, "Failed to copy webengine resources, not applying quirk")
        yield
        return

    if webengine_resources_path is None:
        yield
        return

    _patch(webengine_resources_path / PAK_FILENAME)

    old_value = os.environ.get(RESOURCES_ENV_VAR)
    os.environ[RESOURCES_ENV_VAR] = str(webengine_resources_path)

    yield

    # Restore old value for subprocesses or :restart
    if old_value is None:
        del os.environ[RESOURCES_ENV_VAR]
    else:
        os.environ[RESOURCES_ENV_VAR] = old_value
