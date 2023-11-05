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
from typing import ClassVar, IO, Optional, Dict, Tuple

from qutebrowser.misc import binparsing
from qutebrowser.utils import qtutils, standarddir, version, utils, log

HANGOUTS_MARKER = b"// Extension ID: nkeimhogjdpnpccoofpliimaahmaaome"
HANGOUTS_ID = 36197  # as found by toofar

TARGET_URL = b"https://*.google.com/*"
REPLACEMENT_URL = b"https://*.qb.invalid/*"
assert len(TARGET_URL) == len(REPLACEMENT_URL)


@dataclasses.dataclass
class Pak5Header:

    """Chromium .pak header."""

    encoding: int  # uint32
    resource_count: int  # uint16
    _alias_count: int  # uint16

    _FORMAT: ClassVar[str] = '<IHH'

    @classmethod
    def parse(cls, fobj: IO[bytes]) -> 'Pak5Header':
        """Parse a PAK version 5 header from a file."""
        return cls(*binparsing.unpack(cls._FORMAT, fobj))


@dataclasses.dataclass
class PakEntry:

    """Entry description in a .pak file."""

    resource_id: int  # uint16
    file_offset: int  # uint32
    size: int = 0  # not in file

    _FORMAT: ClassVar[str] = '<HI'

    @classmethod
    def parse(cls, fobj: IO[bytes]) -> 'PakEntry':
        """Parse a PAK entry from a file."""
        return cls(*binparsing.unpack(cls._FORMAT, fobj))


class PakParser:
    """Parse webengine pak and find patch location to disable Google Meet extension."""

    def __init__(self, fobj: IO[bytes]) -> None:
        """Parse the .pak file from the given file object."""
        pak_version = binparsing.unpack("<I", fobj)[0]
        if pak_version != 5:
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

    def _read_header(self) -> Dict[int, PakEntry]:
        """Read the header and entry index from the .pak file."""
        entries = []

        header = Pak5Header.parse(self.fobj)
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

    def _find_manifest(self, entries: Dict[int, PakEntry]) -> Tuple[PakEntry, str]:
        if HANGOUTS_ID in entries:
            suspected_entry = entries[HANGOUTS_ID]
            manifest = self._maybe_get_hangouts_manifest(suspected_entry)
            if manifest is not None:
                return suspected_entry, manifest

        # didn't find it via the previously known ID, let's search them all...
        for id_ in entries:
            manifest = self._maybe_get_hangouts_manifest(entries[id_])
            if manifest is not None:
                return entries[id_], manifest

        raise binparsing.ParseError("Couldn't find hangouts manifest")


def copy_webengine_resources():
    """Copy qtwebengine resources to local dir for patching."""
    resources_dir = qtutils.library_path(qtutils.LibraryPath.data)
    if utils.is_mac:
        # I'm not sure how to arrive at this path without hardcoding it
        # ourselves. importlib_resources("PyQt6.Qt6") can serve as a
        # replacement for the qtutils bit but it doesn't seem to help find the
        # actually Resources folder.
        resources_dir /= "lib" / "QtWebEngineCore.framework" / "Resources"
    else:
        resources_dir /= "resources"
    work_dir = pathlib.Path(standarddir.cache()) / "webengine_resources_pak_quirk"

    log.misc.debug(
        "Copying webengine resources for quirk patching: "
        f"{resources_dir} -> {work_dir}"
    )

    if work_dir.exists():
        # TODO: make backup?
        shutil.rmtree(work_dir)

    shutil.copytree(resources_dir, work_dir)

    os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(work_dir)

    return work_dir


def patch(file_to_patch: pathlib.Path = None):
    """Apply any patches to webengine resource pak files."""
    versions = version.qtwebengine_versions(avoid_init=True)
    if versions.webengine != utils.VersionNumber(6, 6):
        return

    if not file_to_patch:
        try:
            file_to_patch = copy_webengine_resources() / "qtwebengine_resources.pak"
        except OSError:
            log.misc.exception("Failed to copy webengine resources, not applying quirk")
            return

    if not file_to_patch.exists():
        log.misc.error(
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
        except binparsing.ParseError:
            log.misc.exception("Failed to apply quirk to resources pak.")


if __name__ == "__main__":
    output_test_file = pathlib.Path("/tmp/test.pak")
    #shutil.copy("/opt/google/chrome/resources.pak", output_test_file)
    shutil.copy("/usr/share/qt6/resources/qtwebengine_resources.pak", output_test_file)
    patch(output_test_file)

    with open(output_test_file, "rb") as fd:
        reparsed = PakParser(fd)

    print(reparsed.manifest_entry)
    print(reparsed.manifest)
