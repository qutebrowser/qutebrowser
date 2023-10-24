
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

import dataclasses
from typing import ClassVar, IO, Optional, Dict, Tuple

from qutebrowser.misc import binparsing

HANGOUTS_MARKER = b"// Extension ID: nkeimhogjdpnpccoofpliimaahmaaome"
HANGOUTS_ID = 36197  # as found by toofar
PAK_VERSION = 5

TARGET_URL = b"https://*.google.com/*"
REPLACEMENT_URL = b"https://qute.invalid/*"
assert len(TARGET_URL) == len(REPLACEMENT_URL)


@dataclasses.dataclass
class PakHeader:

    """Chromium .pak header (version 5)."""

    encoding: int  # uint32
    resource_count: int  # uint16
    alias_count: int  # uint16

    _FORMAT: ClassVar[str] = '<IHH'

    @classmethod
    def parse(cls, fobj: IO[bytes]) -> 'PakHeader':
        """Parse a PAK version 5 header from a file."""
        return cls(*binparsing.unpack(cls._FORMAT, fobj))


@dataclasses.dataclass
class PakEntry:

    """Entry description in a .pak file"""

    resource_id: int  # uint16
    file_offset: int  # uint32
    size: int = 0  # not in file

    _FORMAT: ClassVar[str] = '<HI'

    @classmethod
    def parse(cls, fobj: IO[bytes]) -> 'PakEntry':
        """Parse a PAK entry from a file."""
        return cls(*binparsing.unpack(cls._FORMAT, fobj))


class PakParser:

    def __init__(self, fobj: IO[bytes]) -> None:
        """Parse the .pak file from the given file object."""
        version = binparsing.unpack("<I", fobj)[0]
        if version != PAK_VERSION:
            raise binparsing.ParseError(f"Unsupported .pak version {version}")

        self.fobj = fobj
        entries = self._read_header()
        self.manifest_entry, self.manifest = self._find_manifest(entries)

    def find_patch_offset(self) -> int:
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

    def _find_manifest(self, entries: Dict[int, PakEntry]) -> Tuple[PakEntry, bytes]:
        if HANGOUTS_ID in entries:
            suspected_entry = entries[HANGOUTS_ID]
            manifest = self._maybe_get_hangouts_manifest(suspected_entry)
            if manifest is not None:
                return suspected_entry, manifest

        # didn't find it via the prevously known ID, let's search them all...
        for entry in entries.values():
            manifest = self._maybe_get_hangouts_manifest(entry)
            if manifest is not None:
                return entry, manifest

        raise binparsing.ParseError("Couldn't find hangouts manifest")


if __name__ == "__main__":
    import shutil
    shutil.copy("/usr/share/qt6/resources/qtwebengine_resources.pak", "/tmp/test.pak")

    with open("/tmp/test.pak", "r+b") as f:
        parser = PakParser(f)
        print(parser.manifest_entry)
        print(parser.manifest)
        offset = parser.find_patch_offset()
        f.seek(offset)
        f.write(REPLACEMENT_URL)

    with open("/tmp/test.pak", "rb") as f:
        parser = PakParser(f)

    print(parser.manifest_entry)
    print(parser.manifest)
