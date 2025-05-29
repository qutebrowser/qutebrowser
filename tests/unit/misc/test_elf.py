# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import io
import struct

import pytest
import hypothesis
from hypothesis import strategies as hst

from qutebrowser.misc import elf, binparsing
from qutebrowser.utils import utils
from qutebrowser.utils.utils import VersionNumber


@pytest.mark.parametrize('fmt, expected', [
    (elf.Ident._FORMAT, 0x10),

    (elf.Header._FORMATS[elf.Bitness.x64], 0x30),
    (elf.Header._FORMATS[elf.Bitness.x32], 0x24),

    (elf.SectionHeader._FORMATS[elf.Bitness.x64], 0x40),
    (elf.SectionHeader._FORMATS[elf.Bitness.x32], 0x28),
])
def test_format_sizes(fmt, expected):
    """Ensure the struct format have the expected sizes.

    See https://en.wikipedia.org/wiki/Executable_and_Linkable_Format#File_header
    and https://en.wikipedia.org/wiki/Executable_and_Linkable_Format#Section_header
    """
    assert struct.calcsize(fmt) == expected


@pytest.mark.skipif(not utils.is_linux, reason="Needs Linux")
def test_result(webengine_versions, qapp, caplog):
    """Test the real result of ELF parsing.

    NOTE: If you're a distribution packager (or contributor) and see this test failing,
    I'd like your help with making either the code or the test more reliable! The
    underlying code is susceptible to changes in the environment, and while it's been
    tested in various environments (Archlinux, Ubuntu), might break in yours.

    If that happens, please report a bug about it!
    """
    pytest.importorskip('qutebrowser.qt.webenginecore')

    versions = elf.parse_webenginecore()
    qtwe_version = webengine_versions.webengine
    if qtwe_version == VersionNumber(5, 15, 19) or qtwe_version >= VersionNumber(6, 5):
        assert versions is None
        pytest.xfail("ELF file structure not supported")

    assert versions is not None

    # No failing mmap
    assert len(caplog.messages) == 2
    assert caplog.messages[0].startswith('QtWebEngine .so found at')
    assert caplog.messages[1].startswith('Got versions from ELF:')

    from qutebrowser.browser.webengine import webenginesettings
    webenginesettings.init_user_agent()
    ua = webenginesettings.parsed_user_agent

    assert ua.qt_version == versions.webengine
    assert ua.upstream_browser_version == versions.chromium


@pytest.mark.parametrize("data, expected", [
    # Simple match
    (
        b"\x00QtWebEngine/5.15.9 Chrome/87.0.4280.144\x00",
        elf.Versions("5.15.9", "87.0.4280.144"),
    ),
    # Ignoring garbage string-like data
    (
        b"\x00QtWebEngine/5.15.9 Chrome/87.0.4xternalclearkey\x00\x00"
        b"QtWebEngine/5.15.9 Chrome/87.0.4280.144\x00",
        elf.Versions("5.15.9", "87.0.4280.144"),
    ),
    # Piecing stuff together
    (
        (
            b"\x00QtWebEngine/6.4.0 Chrome/98.0.47Navigation to external protocol "
            b"blocked by sandb/webengine\x00"
            b"lots-of-other-stuff\x00"
            b"98.0.4758.90\x0099.0.4844.84\x00"
        ),
        elf.Versions("6.4.0", "98.0.4758.90"),
    ),
])
def test_find_versions(data, expected):
    assert elf._find_versions(data) == expected


@pytest.mark.parametrize("data, message", [
    # No match at all
    (
        b"blablabla",
        "No match in .rodata"
    ),
    # Piecing stuff together: too short partial match
    (
        (
            b"\x00QtWebEngine/6.4.0 Chrome/98bla\x00"
            b"lots-of-other-stuff\x00"
            b"98.0.4758.90\x0099.0.4844.84\x00"
        ),
        "Inconclusive partial Chromium bytes"
    ),
    # Piecing stuff together: no full match
    (
        (
            b"\x00QtWebEngine/6.4.0 Chrome/98.0.47blabla"
            b"lots-of-other-stuff\x00"
            b"98.0.1234.56\x00"
        ),
        "No match in .rodata for full version"
    ),
])
def test_find_versions_invalid(data, message):
    with pytest.raises(binparsing.ParseError) as excinfo:
        elf._find_versions(data)
    assert str(excinfo.value) == message


@hypothesis.given(data=hst.builds(
    lambda *a: b''.join(a),
    hst.sampled_from([b'', b'\x7fELF', b'\x7fELF\x02\x01\x01']),
    hst.binary(min_size=0x70),
))
def test_hypothesis(data):
    """Fuzz ELF parsing and make sure no crashes happen."""
    fobj = io.BytesIO(data)
    try:
        elf._parse_from_file(fobj)
    except binparsing.ParseError as e:
        print(e)
