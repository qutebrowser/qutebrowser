# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import io
import json
import struct
import pathlib
import logging

import pytest

from qutebrowser.misc import pakjoy, binparsing
from qutebrowser.utils import utils, version, standarddir


pytest.importorskip("qutebrowser.qt.webenginecore")


versions = version.qtwebengine_versions(avoid_init=True)


@pytest.fixture
def skipifneeded():
    """Used to skip happy path tests with the real resources file.

    Since we don't know how reliably the Google Meet hangouts extensions is
    reliably in the resource files, and this quirk is only targeting 6.6
    anyway.
    """
    if versions.webengine != utils.VersionNumber(6, 6):
        raise pytest.skip("Code under test only runs on 6.6")


@pytest.fixture(autouse=True)
def clean_env():
    yield
    if "QTWEBENGINE_RESOURCES_PATH" in os.environ:
        del os.environ["QTWEBENGINE_RESOURCES_PATH"]


def patch_version(monkeypatch, *args):
    monkeypatch.setattr(
        pakjoy.version,
        "qtwebengine_versions",
        lambda **kwargs: version.WebEngineVersions(
            webengine=utils.VersionNumber(*args),
            chromium=None,
            source="unittest",
        )
    )


@pytest.fixture
def unaffected_version(monkeypatch):
    patch_version(monkeypatch, 6, 6, 1)


@pytest.fixture
def affected_version(monkeypatch):
    patch_version(monkeypatch, 6, 6)


def test_version_gate(unaffected_version, mocker):

    fake_open = mocker.patch("qutebrowser.misc.pakjoy.open")
    pakjoy.patch_webengine()
    assert not fake_open.called


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(pakjoy.standarddir, "cache", lambda: tmp_path)
    return str(tmp_path)


def json_without_comments(bytestring):
    str_without_comments = "\n".join(
        [
            line
            for line in
            bytestring.decode("utf-8").split("\n")
            if not line.strip().startswith("//")
        ]
    )
    return json.loads(str_without_comments)


@pytest.mark.usefixtures("affected_version")
class TestWithRealResourcesFile:
    """Tests that use the real pak file form the Qt installation."""

    def test_happy_path(self, skipifneeded):
        # Go through the full patching processes with the real resources file from
        # the current installation. Make sure our replacement string is in it
        # afterwards.
        pakjoy.patch_webengine()

        patched_resources = pathlib.Path(os.environ["QTWEBENGINE_RESOURCES_PATH"])

        with open(patched_resources / "qtwebengine_resources.pak", "rb") as fd:
            reparsed = pakjoy.PakParser(fd)

        json_manifest = json_without_comments(reparsed.manifest)

        assert pakjoy.REPLACEMENT_URL.decode("utf-8") in json_manifest[
            "externally_connectable"
        ]["matches"]

    def test_copying_resources(self):
        # Test we managed to copy some files over
        work_dir = pakjoy.copy_webengine_resources()

        assert work_dir.exists()
        assert work_dir == standarddir.cache() / "webengine_resources_pak_quirk"
        assert (work_dir / "qtwebengine_resources.pak").exists()
        assert len(list(work_dir.glob("*"))) > 1

    def test_copying_resources_overwrites(self):
        work_dir = pakjoy.copy_webengine_resources()
        tmpfile = work_dir / "tmp.txt"
        tmpfile.touch()

        pakjoy.copy_webengine_resources()
        assert not tmpfile.exists()

    @pytest.mark.parametrize("osfunc", ["copytree", "rmtree"])
    def test_copying_resources_oserror(self, monkeypatch, caplog, osfunc):
        # Test errors from the calls to shutil are handled
        pakjoy.copy_webengine_resources()  # run twice so we hit rmtree too
        caplog.clear()

        def raiseme(err):
            raise err

        monkeypatch.setattr(pakjoy.shutil, osfunc, lambda *_args: raiseme(PermissionError(osfunc)))
        with caplog.at_level(logging.ERROR, "misc"):
            pakjoy.patch_webengine()
        assert caplog.messages == ["Failed to copy webengine resources, not applying quirk"]

    def test_expected_file_not_found(self, tmp_cache, monkeypatch, caplog):
        with caplog.at_level(logging.ERROR, "misc"):
            pakjoy._patch(pathlib.Path(tmp_cache) / "doesntexist")
        assert caplog.messages[-1].startswith(
            "Resource pak doesn't exist at expected location! "
            "Not applying quirks. Expected location: "
        )


def json_manifest_factory(extension_id=pakjoy.HANGOUTS_MARKER, url=pakjoy.TARGET_URL):
    assert isinstance(extension_id, bytes)
    assert isinstance(url, bytes)

    return f"""
    {{
      {extension_id.decode("utf-8")}
      "key": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDAQt2ZDdPfoSe/JI6ID5bgLHRCnCu9T36aYczmhw/tnv6QZB2I6WnOCMZXJZlRdqWc7w9jo4BWhYS50Vb4weMfh/I0On7VcRwJUgfAxW2cHB+EkmtI1v4v/OU24OqIa1Nmv9uRVeX0GjhQukdLNhAE6ACWooaf5kqKlCeK+1GOkQIDAQAB",
      "name": "Google Hangouts",
      // Note: Always update the version number when this file is updated. Chrome
      // triggers extension preferences update on the version increase.
      "version": "1.3.21",
      "manifest_version": 2,
      "externally_connectable": {{
        "matches": [
          "{url.decode("utf-8")}",
          "http://localhost:*/*"
        ]
        }}
    }}
    """.strip().encode("utf-8")


def pak_factory(version=5, entries=None, encoding=1, sentinel_position=-1):
    if entries is None:
        entries = [json_manifest_factory()]

    buffer = io.BytesIO()
    buffer.write(struct.pack("<I", version))
    buffer.write(struct.pack(pakjoy.PakHeader._FORMAT, encoding, len(entries), 0))

    entry_headers_size = (len(entries) + 1) * 6
    start_of_data = buffer.tell() + entry_headers_size

    # Normally the sentinel sits between the headers and the data. But to get
    # full coverage we want to insert it in other positions.
    with_indices = list(enumerate(entries, 1))
    if sentinel_position == -1:
        with_indices.append((0, b""))
    elif sentinel_position is not None:
        with_indices.insert(sentinel_position, (0, b""))

    accumulated_data_offset = start_of_data
    for idx, entry in with_indices:
        buffer.write(struct.pack(pakjoy.PakEntry._FORMAT, idx, accumulated_data_offset))
        accumulated_data_offset += len(entry)

    for entry in entries:
        assert isinstance(entry, bytes)
        buffer.write(entry)

    buffer.seek(0)
    return buffer


@pytest.mark.usefixtures("affected_version")
class TestWithConstructedResourcesFile:
    """Tests that use a constructed pak file to give us more control over it."""

    def test_happy_path(self):
        buffer = pak_factory()

        parser = pakjoy.PakParser(buffer)

        json_manifest = json_without_comments(parser.manifest)

        assert pakjoy.TARGET_URL.decode("utf-8") in json_manifest[
            "externally_connectable"
        ]["matches"]

    def test_bad_version(self):
        buffer = pak_factory(version=99)

        with pytest.raises(
            binparsing.ParseError,
            match="Unsupported .pak version 99",
        ):
            pakjoy.PakParser(buffer)

    @pytest.mark.parametrize("position, error", [
        (0, "Unexpected sentinel entry"),
        (None, "Missing sentinel entry"),
    ])
    def test_bad_sentinal_position(self, position, error):
        buffer = pak_factory(sentinel_position=position)

        with pytest.raises(binparsing.ParseError):
            pakjoy.PakParser(buffer)

    @pytest.mark.parametrize("entry", [
        b"{foo}",
        b"V2VsbCBoZWxsbyB0aGVyZQo=",
    ])
    def test_marker_not_found(self, entry):
        buffer = pak_factory(entries=[entry])

        with pytest.raises(
            binparsing.ParseError,
            match="Couldn't find hangouts manifest",
        ):
            pakjoy.PakParser(buffer)

    def test_url_not_found(self):
        buffer = pak_factory(entries=[json_manifest_factory(url=b"example.com")])

        parser = pakjoy.PakParser(buffer)
        with pytest.raises(
            binparsing.ParseError,
            match="Couldn't find URL in manifest",
        ):
            parser.find_patch_offset()

    def test_url_not_found_high_level(self, tmp_cache, caplog,
                                      affected_version):
        buffer = pak_factory(entries=[json_manifest_factory(url=b"example.com")])

        # Write bytes to file so we can test pakjoy._patch()
        tmpfile = pathlib.Path(tmp_cache) / "bad.pak"
        with open(tmpfile, "wb") as fd:
            fd.write(buffer.read())

        with caplog.at_level(logging.ERROR, "misc"):
            pakjoy._patch(tmpfile)

        assert caplog.messages == [
            "Failed to apply quirk to resources pak."
        ]
