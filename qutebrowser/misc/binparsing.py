# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities for parsing binary files.

Used by elf.py as well as pakjoy.py.
"""

import struct
from typing import Any, IO


class ParseError(Exception):

    """Raised when the file can't be parsed."""


def unpack(fmt: str, fobj: IO[bytes]) -> tuple[Any, ...]:
    """Unpack the given struct format from the given file."""
    size = struct.calcsize(fmt)
    data = safe_read(fobj, size)

    try:
        return struct.unpack(fmt, data)
    except struct.error as e:
        raise ParseError(e)


def safe_read(fobj: IO[bytes], size: int) -> bytes:
    """Read from a file, handling possible exceptions."""
    try:
        return fobj.read(size)
    except (OSError, OverflowError) as e:
        raise ParseError(e)


def safe_seek(fobj: IO[bytes], pos: int) -> None:
    """Seek in a file, handling possible exceptions."""
    try:
        fobj.seek(pos)
    except (OSError, OverflowError) as e:
        raise ParseError(e)
