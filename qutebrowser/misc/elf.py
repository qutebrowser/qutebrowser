# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Simplistic ELF parser to get the QtWebEngine/Chromium versions.

I know what you must be thinking when reading this: "Why on earth does qutebrowser have
an ELF parser?!". For one, because writing one was an interesting learning exercise. But
there's actually a reason it's here: QtWebEngine 5.15.x versions come with different
underlying Chromium versions, but there is no API to get the version of
QtWebEngine/Chromium...

We can instead:

a) Look at the Qt runtime version (qVersion()). This often doesn't actually correspond
to the QtWebEngine version (as that can be older/newer). Since there will be a
QtWebEngine 5.15.3 release, but not Qt itself (due to LTS licensing restrictions), this
isn't a reliable source of information.

b) Look at the PyQtWebEngine version (PyQt5.QtWebEngine.PYQT_WEBENGINE_VERSION_STR).
This is a good first guess (especially for our Windows/macOS releases), but still isn't
certain. Linux distributions often push a newer QtWebEngine before the corresponding
PyQtWebEngine release, and some (*cough* Gentoo *cough*) even publish QtWebEngine
"5.15.2" but upgrade the underlying Chromium.

c) Parse the user agent. This is what qutebrowser did before this monstrosity was
introduced (and still does as a fallback), but for some things (finding the proper
commandline arguments to pass) it's too late in the initialization process.

d) Spawn QtWebEngine in a subprocess and ask for its user-agent. This takes too long to
do it on every startup.

e) Ask the package manager for this information. This means we'd need to know (or guess)
the package manager and package name. Also see:
https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=752114

Because of all those issues, we instead look for the (fixed!) version string as part of
the user agent header. Because libQt5WebEngineCore is rather big (~120 MB), we don't
want to search through the entire file, so we instead have a simplistic ELF parser here
to find the .rodata section. This way, searching the version gets faster by some orders
of magnitudes (a couple of us instead of ms).

This is a "best effort" parser. If it errors out, we instead end up relying on the
PyQtWebEngine version, which is the next best thing.
"""

import enum
import re
import dataclasses
import mmap
import pathlib
from typing import IO, ClassVar, Optional, cast

from qutebrowser.qt import machinery
from qutebrowser.utils import log, version, qtutils
from qutebrowser.misc import binparsing


class Bitness(enum.Enum):

    """Whether the ELF file is 32- or 64-bit."""

    x32 = 1
    x64 = 2


class Endianness(enum.Enum):

    """Whether the ELF file is little- or big-endian."""

    little = 1
    big = 2


@dataclasses.dataclass
class Ident:

    """File identification for ELF.

    See https://en.wikipedia.org/wiki/Executable_and_Linkable_Format#File_header
    (first 16 bytes).
    """

    magic: bytes
    klass: Bitness
    data: Endianness
    version: int
    osabi: int
    abiversion: int

    _FORMAT: ClassVar[str] = '<4sBBBBB7x'

    @classmethod
    def parse(cls, fobj: IO[bytes]) -> 'Ident':
        """Parse an ELF ident header from a file."""
        magic, klass, data, elfversion, osabi, abiversion = binparsing.unpack(cls._FORMAT, fobj)

        try:
            bitness = Bitness(klass)
        except ValueError:
            raise binparsing.ParseError(f"Invalid bitness {klass}")

        try:
            endianness = Endianness(data)
        except ValueError:
            raise binparsing.ParseError(f"Invalid endianness {data}")

        return cls(magic, bitness, endianness, elfversion, osabi, abiversion)


@dataclasses.dataclass
class Header:

    """ELF header without file identification.

    See https://en.wikipedia.org/wiki/Executable_and_Linkable_Format#File_header
    (without the first 16 bytes).
    """

    typ: int
    machine: int
    version: int
    entry: int
    phoff: int
    shoff: int
    flags: int
    ehsize: int
    phentsize: int
    phnum: int
    shentsize: int
    shnum: int
    shstrndx: int

    _FORMATS: ClassVar[dict[Bitness, str]] = {
        Bitness.x64: '<HHIQQQIHHHHHH',
        Bitness.x32: '<HHIIIIIHHHHHH',
    }

    @classmethod
    def parse(cls, fobj: IO[bytes], bitness: Bitness) -> 'Header':
        """Parse an ELF header from a file."""
        fmt = cls._FORMATS[bitness]
        return cls(*binparsing.unpack(fmt, fobj))


@dataclasses.dataclass
class SectionHeader:

    """ELF section header.

    See https://en.wikipedia.org/wiki/Executable_and_Linkable_Format#Section_header
    """

    name: int
    typ: int
    flags: int
    addr: int
    offset: int
    size: int
    link: int
    info: int
    addralign: int
    entsize: int

    _FORMATS: ClassVar[dict[Bitness, str]] = {
        Bitness.x64: '<IIQQQQIIQQ',
        Bitness.x32: '<IIIIIIIIII',
    }

    @classmethod
    def parse(cls, fobj: IO[bytes], bitness: Bitness) -> 'SectionHeader':
        """Parse an ELF section header from a file."""
        fmt = cls._FORMATS[bitness]
        return cls(*binparsing.unpack(fmt, fobj))


def get_rodata_header(f: IO[bytes]) -> SectionHeader:
    """Parse an ELF file and find the .rodata section header."""
    ident = Ident.parse(f)
    if ident.magic != b'\x7fELF':
        raise binparsing.ParseError(f"Invalid magic {ident.magic!r}")

    if ident.data != Endianness.little:
        raise binparsing.ParseError("Big endian is unsupported")

    if ident.version != 1:
        raise binparsing.ParseError(f"Only version 1 is supported, not {ident.version}")

    header = Header.parse(f, bitness=ident.klass)

    # Read string table
    binparsing.safe_seek(f, header.shoff + header.shstrndx * header.shentsize)
    shstr = SectionHeader.parse(f, bitness=ident.klass)

    binparsing.safe_seek(f, shstr.offset)
    string_table = binparsing.safe_read(f, shstr.size)

    # Back to all sections
    for i in range(header.shnum):
        binparsing.safe_seek(f, header.shoff + i * header.shentsize)
        sh = SectionHeader.parse(f, bitness=ident.klass)
        name = string_table[sh.name:].split(b'\x00')[0]
        if name == b'.rodata':
            return sh

    raise binparsing.ParseError("No .rodata section found")


@dataclasses.dataclass
class Versions:

    """The versions found in the ELF file."""

    webengine: str
    chromium: str


def _find_versions(data: bytes) -> Versions:
    """Find the version numbers in the given data.

    Note that 'data' can actually be a mmap.mmap, but typing doesn't handle that
    correctly: https://github.com/python/typeshed/issues/1467
    """
    pattern = br'\x00QtWebEngine/([0-9.]+) Chrome/([0-9.]+)\x00'
    match = re.search(pattern, data)
    if match is not None:
        try:
            return Versions(
                webengine=match.group(1).decode('ascii'),
                chromium=match.group(2).decode('ascii'),
            )
        except UnicodeDecodeError as e:
            raise binparsing.ParseError(e)

    # Here it gets even more crazy: Sometimes, we don't have the full UA in one piece
    # in the string table somehow (?!). However, Qt 6.2 added a separate
    # qWebEngineChromiumVersion(), with PyQt wrappers following later. And *that*
    # apparently stores the full version in the string table separately from the UA.
    # As we clearly didn't have enough crazy heuristics yet so far, let's hunt for it!

    # We first get the partial Chromium version from the UA:
    match = re.search(pattern[:-4], data)  # without trailing literal \x00
    if match is None:
        raise binparsing.ParseError("No match in .rodata")

    webengine_bytes = match.group(1)
    partial_chromium_bytes = match.group(2)
    if b"." not in partial_chromium_bytes or len(partial_chromium_bytes) < 6:
        # some sanity checking
        raise binparsing.ParseError("Inconclusive partial Chromium bytes")

    # And then try to find the *full* string, stored separately, based on the
    # partial one we got above.
    pattern = br"\x00(" + re.escape(partial_chromium_bytes) + br"[0-9.]+)\x00"
    match = re.search(pattern, data)
    if match is None:
        raise binparsing.ParseError("No match in .rodata for full version")

    chromium_bytes = match.group(1)
    try:
        return Versions(
            webengine=webengine_bytes.decode('ascii'),
            chromium=chromium_bytes.decode('ascii'),
        )
    except UnicodeDecodeError as e:
        raise binparsing.ParseError(e)


def _parse_from_file(f: IO[bytes]) -> Versions:
    """Parse the ELF file from the given path."""
    sh = get_rodata_header(f)

    rest = sh.offset % mmap.ALLOCATIONGRANULARITY
    mmap_offset = sh.offset - rest
    mmap_size = sh.size + rest

    try:
        with mmap.mmap(
            f.fileno(),
            mmap_size,
            offset=mmap_offset,
            access=mmap.ACCESS_READ,
        ) as mmap_data:
            return _find_versions(cast(bytes, mmap_data))
    except (OSError, OverflowError) as e:
        log.misc.debug(f"mmap failed ({e}), falling back to reading", exc_info=True)
        binparsing.safe_seek(f, sh.offset)
        data = binparsing.safe_read(f, sh.size)
        return _find_versions(data)


def parse_webenginecore() -> Optional[Versions]:
    """Parse the QtWebEngineCore library file."""
    if version.is_flatpak():
        # Flatpak has Qt in /usr/lib/x86_64-linux-gnu, but QtWebEngine in /app/lib.
        library_path = pathlib.Path("/app/lib")
    else:
        library_path = qtutils.library_path(qtutils.LibraryPath.libraries)

    suffix = "6" if machinery.IS_QT6 else "5"
    library_name = sorted(library_path.glob(f'libQt{suffix}WebEngineCore.so*'))
    if not library_name:
        log.misc.debug(f"No QtWebEngine .so found in {library_path}")
        return None
    else:
        lib_file = library_name[-1]
        log.misc.debug(f"QtWebEngine .so found at {lib_file}")

    try:
        with lib_file.open('rb') as f:
            versions = _parse_from_file(f)

        log.misc.debug(f"Got versions from ELF: {versions}")
        return versions
    except binparsing.ParseError as e:
        log.misc.debug(f"Failed to parse ELF: {e}", exc_info=True)
        return None
