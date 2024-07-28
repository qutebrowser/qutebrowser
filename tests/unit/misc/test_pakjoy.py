# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import io
import json
import struct
import pathlib
import logging
import shutil

import pytest

from qutebrowser.misc import pakjoy, binparsing
from qutebrowser.utils import utils, version, standarddir, usertypes


pytest.importorskip("qutebrowser.qt.webenginecore")


pytestmark = pytest.mark.usefixtures("cache_tmpdir")


versions = version.qtwebengine_versions(avoid_init=True)


@pytest.fixture(autouse=True)
def prepare_env(qapp, monkeypatch):
    monkeypatch.setattr(pakjoy.objects, "qapp", qapp)
    monkeypatch.delenv(pakjoy.RESOURCES_ENV_VAR, raising=False)
    monkeypatch.delenv(pakjoy.DISABLE_ENV_VAR, raising=False)


def patch_version(monkeypatch: pytest.MonkeyPatch, qtwe_version: utils.VersionNumber):
    monkeypatch.setattr(
        pakjoy.version,
        "qtwebengine_versions",
        lambda **kwargs: version.WebEngineVersions(
            webengine=qtwe_version,
            chromium=None,
            source="unittest",
        ),
    )


@pytest.fixture(params=[
    utils.VersionNumber(6, 4),
    utils.VersionNumber(6, 5, 3),
    utils.VersionNumber(6, 6, 1),
    utils.VersionNumber(6, 7),
])
def unaffected_version(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest, config_stub):
    config_stub.val.colors.webpage.darkmode.enabled = True
    patch_version(monkeypatch, request.param)


@pytest.fixture(params=[
    utils.VersionNumber(6, 5),
    utils.VersionNumber(6, 5, 1),
    utils.VersionNumber(6, 5, 2),
    utils.VersionNumber(6, 6),
])
def affected_version(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest, config_stub):
    config_stub.val.colors.webpage.darkmode.enabled = True
    patch_version(monkeypatch, request.param)


@pytest.mark.parametrize("workdir_exists", [True, False])
def test_version_gate(cache_tmpdir, unaffected_version, mocker, config_stub, workdir_exists):
    workdir = cache_tmpdir / pakjoy.CACHE_DIR_NAME
    if workdir_exists:
        workdir.mkdir()
        (workdir / "some_patched_file.pak").ensure()
    fake_open = mocker.patch("qutebrowser.misc.pakjoy.open")

    with pakjoy.patch_webengine():
        pass

    assert not fake_open.called
    assert not workdir.exists()


@pytest.mark.parametrize("explicit", [True, False])
def test_escape_hatch(affected_version, mocker, monkeypatch, config_stub, explicit):
    config_stub.val.qt.workarounds.disable_hangouts_extension = explicit
    fake_open = mocker.patch("qutebrowser.misc.pakjoy.open")
    monkeypatch.setenv(pakjoy.DISABLE_ENV_VAR, "1")

    with pakjoy.patch_webengine():
        pass

    assert not fake_open.called


class TestFindWebengineResources:
    @pytest.fixture
    def qt_data_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path):
        """Patch qtutils.library_path() to return a temp dir."""
        qt_data_path = tmp_path / "qt_data"
        qt_data_path.mkdir()
        monkeypatch.setattr(pakjoy.qtutils, "library_path", lambda _which: qt_data_path)
        return qt_data_path

    @pytest.fixture
    def application_dir_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path,
        qt_data_path: pathlib.Path,  # needs patching
    ):
        """Patch QApplication.applicationDirPath() to return a temp dir."""
        app_dir_path = tmp_path / "app_dir"
        app_dir_path.mkdir()
        monkeypatch.setattr(
            pakjoy.objects.qapp, "applicationDirPath", lambda: app_dir_path
        )
        return app_dir_path

    @pytest.fixture
    def fallback_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path,
        qt_data_path: pathlib.Path,  # needs patching
        application_dir_path: pathlib.Path,  # needs patching
    ):
        """Patch the fallback path to return a temp dir."""
        home_path = tmp_path / "home"
        monkeypatch.setattr(pakjoy.pathlib.Path, "home", lambda: home_path)

        app_path = home_path / f".{pakjoy.objects.qapp.applicationName()}"
        app_path.mkdir(parents=True)
        return app_path

    @pytest.mark.parametrize("create_file", [True, False])
    def test_overridden(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, create_file: bool
    ):
        """Test the overridden path is used."""
        override_path = tmp_path / "override"
        override_path.mkdir()
        monkeypatch.setenv(pakjoy.RESOURCES_ENV_VAR, str(override_path))
        if create_file:  # should get this no matter if file exists or not
            (override_path / pakjoy.PAK_FILENAME).touch()
        assert pakjoy._find_webengine_resources() == override_path

    @pytest.mark.parametrize("with_subfolder", [True, False])
    def test_qt_data_path(self, qt_data_path: pathlib.Path, with_subfolder: bool):
        """Test qtutils.library_path() is used."""
        resources_path = qt_data_path
        if with_subfolder:
            resources_path /= "resources"
            resources_path.mkdir()
        (resources_path / pakjoy.PAK_FILENAME).touch()
        assert pakjoy._find_webengine_resources() == resources_path

    def test_application_dir_path(self, application_dir_path: pathlib.Path):
        """Test QApplication.applicationDirPath() is used."""
        (application_dir_path / pakjoy.PAK_FILENAME).touch()
        assert pakjoy._find_webengine_resources() == application_dir_path

    def test_fallback_path(self, fallback_path: pathlib.Path):
        """Test fallback path is used."""
        (fallback_path / pakjoy.PAK_FILENAME).touch()
        assert pakjoy._find_webengine_resources() == fallback_path

    def test_nowhere(self, fallback_path: pathlib.Path):
        """Test we raise if we can't find the resources."""
        with pytest.raises(
            FileNotFoundError, match="Couldn't find webengine resources dir, candidates:\n*"
        ):
            pakjoy._find_webengine_resources()


def json_without_comments(bytestring):
    str_without_comments = "\n".join(
        [
            line
            for line in bytestring.decode("utf-8").split("\n")
            if not line.strip().startswith("//")
        ]
    )
    return json.loads(str_without_comments)


def read_patched_manifest():
    patched_resources = pathlib.Path(os.environ[pakjoy.RESOURCES_ENV_VAR])

    with open(patched_resources / pakjoy.PAK_FILENAME, "rb") as fd:
        reparsed = pakjoy.PakParser(fd)

    return json_without_comments(reparsed.manifest)


@pytest.mark.usefixtures("affected_version")
class TestWithRealResourcesFile:
    """Tests that use the real pak file form the Qt installation."""

    @pytest.mark.qt6_only
    def test_happy_path(self):
        # Go through the full patching processes with the real resources file from
        # the current installation. Make sure our replacement string is in it
        # afterwards.
        with pakjoy.patch_webengine():
            json_manifest = read_patched_manifest()

        assert (
            pakjoy.REPLACEMENT_URL.decode("utf-8")
            in json_manifest["externally_connectable"]["matches"]
        )

    def test_copying_resources(self):
        # Test we managed to copy some files over
        work_dir = pakjoy.copy_webengine_resources()

        assert work_dir is not None
        assert work_dir.exists()
        assert work_dir == pathlib.Path(standarddir.cache()) / pakjoy.CACHE_DIR_NAME
        assert (work_dir / pakjoy.PAK_FILENAME).exists()
        assert len(list(work_dir.glob("*"))) > 1

    def test_copying_resources_overwrites(self):
        work_dir = pakjoy.copy_webengine_resources()
        assert work_dir is not None
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

        monkeypatch.setattr(
            pakjoy.shutil, osfunc, lambda *_args: raiseme(PermissionError(osfunc))
        )
        with caplog.at_level(logging.ERROR, "misc"):
            with pakjoy.patch_webengine():
                pass

        assert caplog.messages == [
            "Failed to copy webengine resources, not applying quirk"
        ]

    def test_expected_file_not_found(self, cache_tmpdir, monkeypatch, caplog):
        with caplog.at_level(logging.ERROR, "misc"):
            pakjoy._patch(pathlib.Path(cache_tmpdir) / "doesntexist")
        assert caplog.messages[-1].startswith(
            "Resource pak doesn't exist at expected location! "
            "Not applying quirks. Expected location: "
        )

    @pytest.mark.qt6_only
    def test_hardcoded_ids(self):
        """Make sure we hardcoded the currently valid ID.

        This avoids users having to iterate through the whole resource file on
        every start. It will probably break on every QtWebEngine upgrade and can
        be fixed by adding the respective ID to HANGOUTS_IDS.
        """
        resources_dir = pakjoy._find_webengine_resources()
        file_to_patch = resources_dir / pakjoy.PAK_FILENAME
        with open(file_to_patch, "rb") as f:
            parser = pakjoy.PakParser(f)
        error_msg = (
            "Encountered hangouts extension with resource ID which isn't in pakjoy.HANGOUTS_IDS: "
            f"found_resource_id={parser.manifest_entry.resource_id} "
            f"webengine_version={versions.webengine}"
        )
        assert parser.manifest_entry.resource_id in pakjoy.HANGOUTS_IDS, error_msg


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
    """.strip().encode(
        "utf-8"
    )


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

    @pytest.mark.parametrize(
        "offset",
        [0, 42, *pakjoy.HANGOUTS_IDS],  # test both slow search and fast path
    )
    def test_happy_path(self, offset):
        entries = [b""] * offset + [json_manifest_factory()]
        assert entries[offset] != b""
        buffer = pak_factory(entries=entries)

        parser = pakjoy.PakParser(buffer)

        json_manifest = json_without_comments(parser.manifest)

        assert (
            pakjoy.TARGET_URL.decode("utf-8")
            in json_manifest["externally_connectable"]["matches"]
        )

    def test_bad_version(self):
        buffer = pak_factory(version=99)

        with pytest.raises(
            binparsing.ParseError,
            match="Unsupported .pak version 99",
        ):
            pakjoy.PakParser(buffer)

    @pytest.mark.parametrize(
        "position, error",
        [
            (0, "Unexpected sentinel entry"),
            (None, "Missing sentinel entry"),
        ],
    )
    def test_bad_sentinal_position(self, position, error):
        buffer = pak_factory(sentinel_position=position)

        with pytest.raises(binparsing.ParseError):
            pakjoy.PakParser(buffer)

    @pytest.mark.parametrize(
        "entry",
        [
            b"{foo}",
            b"V2VsbCBoZWxsbyB0aGVyZQo=",
        ],
    )
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

    @pytest.mark.parametrize("explicit", [True, False])
    def test_url_not_found_high_level(self, cache_tmpdir, caplog, affected_version, config_stub, message_mock, explicit):
        config_stub.val.qt.workarounds.disable_hangouts_extension = explicit
        buffer = pak_factory(entries=[json_manifest_factory(url=b"example.com")])

        # Write bytes to file so we can test pakjoy._patch()
        tmpfile = pathlib.Path(cache_tmpdir) / "bad.pak"
        with open(tmpfile, "wb") as fd:
            fd.write(buffer.read())

        logger = "message" if explicit else "misc"
        with caplog.at_level(logging.ERROR, logger):
            pakjoy._patch(tmpfile)

        if explicit:
            msg = message_mock.getmsg(usertypes.MessageLevel.error)
            assert msg.text == (
                "Failed to disable Hangouts extension:\n"
                "Failed to apply quirk to resources pak."
            )
        else:
            assert caplog.messages[-1] == "Failed to apply quirk to resources pak."

    @pytest.fixture
    def resources_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> pathlib.Path:
        resources_path = tmp_path / "resources"
        resources_path.mkdir()

        buffer = pak_factory()
        with open(resources_path / pakjoy.PAK_FILENAME, "wb") as fd:
            fd.write(buffer.read())

        monkeypatch.setattr(pakjoy.qtutils, "library_path", lambda _which: tmp_path)
        return resources_path

    @pytest.fixture
    def quirk_dir_path(self, tmp_path: pathlib.Path) -> pathlib.Path:
        return tmp_path / "cache" / pakjoy.CACHE_DIR_NAME

    def test_patching(self, resources_path: pathlib.Path, quirk_dir_path: pathlib.Path):
        """Go through the full patching processes with a fake resources file."""
        with pakjoy.patch_webengine():
            assert os.environ[pakjoy.RESOURCES_ENV_VAR] == str(quirk_dir_path)
            json_manifest = read_patched_manifest()

        assert (
            pakjoy.REPLACEMENT_URL.decode("utf-8")
            in json_manifest["externally_connectable"]["matches"]
        )
        assert pakjoy.RESOURCES_ENV_VAR not in os.environ

    @pytest.mark.qt6_only
    def test_explicitly_enabled(self, monkeypatch: pytest.MonkeyPatch, config_stub):
        patch_version(monkeypatch, utils.VersionNumber(6, 7))  # unaffected
        config_stub.val.qt.workarounds.disable_hangouts_extension = True
        with pakjoy.patch_webengine():
            assert pakjoy.RESOURCES_ENV_VAR in os.environ

    def test_preset_env_var(
        self,
        resources_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        quirk_dir_path: pathlib.Path,
    ):
        new_resources_path = resources_path.with_name(resources_path.name + "_moved")
        shutil.move(resources_path, new_resources_path)
        monkeypatch.setenv(pakjoy.RESOURCES_ENV_VAR, str(new_resources_path))

        with pakjoy.patch_webengine():
            assert os.environ[pakjoy.RESOURCES_ENV_VAR] == str(quirk_dir_path)

        assert os.environ[pakjoy.RESOURCES_ENV_VAR] == str(new_resources_path)
