# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Functions related to host blocking."""

import os.path
import posixpath
import zipfile
import logging
import pathlib
from typing import cast, IO, Set

from PyQt5.QtCore import QUrl

from qutebrowser.api import (
    hook,
    config,
    message,
    interceptor,
    apitypes,
    qtutils,
)
from qutebrowser.components.utils import blockutils
from qutebrowser.utils import version  # FIXME: Move needed parts into api namespace?


logger = logging.getLogger("network")
host_blocker = cast("HostBlocker", None)


def _guess_zip_filename(zf: zipfile.ZipFile) -> str:
    """Guess which file to use inside a zip file."""
    files = zf.namelist()
    if len(files) == 1:
        return files[0]
    else:
        for e in files:
            if posixpath.splitext(e)[0].lower() == "hosts":
                return e
    raise FileNotFoundError("No hosts file found in zip")


def get_fileobj(byte_io: IO[bytes]) -> IO[bytes]:
    """Get a usable file object to read the hosts file from."""
    byte_io.seek(0)  # rewind downloaded file
    if zipfile.is_zipfile(byte_io):
        byte_io.seek(0)  # rewind what zipfile.is_zipfile did
        zf = zipfile.ZipFile(byte_io)
        filename = _guess_zip_filename(zf)
        byte_io = zf.open(filename, mode="r")
    else:
        byte_io.seek(0)  # rewind what zipfile.is_zipfile did
    return byte_io


def _should_be_used() -> bool:
    """Whether the hostblocker should be used or not."""
    method = config.val.content.blocking.method

    adblock_info = version.MODULE_INFO["adblock"]
    adblock_usable = adblock_info.is_usable()

    logger.debug(f"Configured adblock method {method}, adblock library usable: "
                 f"{adblock_usable}")
    return method in ("both", "hosts") or (method == "auto" and not adblock_usable)


class HostBlocker:

    """Manage blocked hosts based from /etc/hosts-like files.

    Attributes:
        enabled: Given the current blocking method, should the host blocker be enabled?
        _blocked_hosts: A set of blocked hosts.
        _config_blocked_hosts: A set of blocked hosts from ~/.config.
        _local_hosts_file: The path to the blocked-hosts file.
        _config_hosts_file: The path to a blocked-hosts in ~/.config
        _has_basedir: Whether a custom --basedir is set.
    """

    def __init__(
        self,
        *,
        data_dir: pathlib.Path,
        config_dir: pathlib.Path,
        has_basedir: bool = False
    ) -> None:
        self.enabled = _should_be_used()
        self._has_basedir = has_basedir
        self._blocked_hosts: Set[str] = set()
        self._config_blocked_hosts: Set[str] = set()

        self._local_hosts_file = str(data_dir / "blocked-hosts")
        self.update_files()

        self._config_hosts_file = str(config_dir / "blocked-hosts")

    def _is_blocked(self, request_url: QUrl, first_party_url: QUrl = None) -> bool:
        """Check whether the given request is blocked."""
        if not self.enabled:
            return False

        if first_party_url is not None and not first_party_url.isValid():
            first_party_url = None

        qtutils.ensure_valid(request_url)

        if not config.get("content.blocking.enabled", url=first_party_url):
            return False

        host = request_url.host()
        return (
            host in self._blocked_hosts or host in self._config_blocked_hosts
        ) and not blockutils.is_whitelisted_url(request_url)

    def filter_request(self, info: interceptor.Request) -> None:
        """Block the given request if necessary."""
        if self._is_blocked(
            request_url=info.request_url, first_party_url=info.first_party_url
        ):
            logger.debug(
                "Request to {} blocked by host blocker.".format(info.request_url.host())
            )
            info.block()

    def _read_hosts_line(self, raw_line: bytes) -> Set[str]:
        """Read hosts from the given line.

        Args:
            line: The bytes object to read.

        Returns:
            A set containing valid hosts found
            in the line.
        """
        if raw_line.startswith(b"#"):
            # Ignoring comments early so we don't have to care about
            # encoding errors in them
            return set()

        line = raw_line.decode("utf-8")

        # Remove comments
        hash_idx = line.find("#")
        line = line if hash_idx == -1 else line[:hash_idx]

        parts = line.strip().split()
        if len(parts) == 1:
            # "one host per line" format
            hosts = parts
        else:
            # /etc/hosts format
            hosts = parts[1:]

        filtered_hosts = set()
        for host in hosts:
            if "." in host and not host.endswith(".localdomain") and host != "0.0.0.0":
                filtered_hosts.update([host])

        return filtered_hosts

    def _read_hosts_file(self, filename: str, target: Set[str]) -> bool:
        """Read hosts from the given filename.

        Args:
            filename: The file to read.
            target: The set to store the hosts in.

        Return:
            True if a read was attempted, False otherwise
        """
        if not os.path.exists(filename):
            return False

        try:
            with open(filename, "rb") as f:
                for line in f:
                    target |= self._read_hosts_line(line)

        except (OSError, UnicodeDecodeError):
            logger.exception("Failed to read host blocklist!")

        return True

    def read_hosts(self) -> None:
        """Read hosts from the existing blocked-hosts file."""
        self._blocked_hosts = set()

        self._read_hosts_file(self._config_hosts_file, self._config_blocked_hosts)

        found = self._read_hosts_file(self._local_hosts_file, self._blocked_hosts)

        if not found:
            if (
                config.val.content.blocking.hosts.lists
                and not self._has_basedir
                and config.val.content.blocking.enabled
                and self.enabled
            ):
                message.info("Run :adblock-update to get adblock lists.")

    def adblock_update(self) -> blockutils.BlocklistDownloads:
        """Update the adblock block lists."""
        self._read_hosts_file(self._config_hosts_file, self._config_blocked_hosts)
        self._blocked_hosts = set()

        blocklists = config.val.content.blocking.hosts.lists
        dl = blockutils.BlocklistDownloads(blocklists)
        dl.single_download_finished.connect(self._merge_file)
        dl.all_downloads_finished.connect(self._on_lists_downloaded)
        dl.initiate()
        return dl

    def _merge_file(self, byte_io: IO[bytes]) -> None:
        """Read and merge host files.

        Args:
            byte_io: The BytesIO object of the completed download.
        """
        error_count = 0
        line_count = 0
        try:
            f = get_fileobj(byte_io)
        except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, LookupError) as e:
            message.error(
                "hostblock: Error while reading {}: {} - {}".format(
                    byte_io.name, e.__class__.__name__, e
                )
            )
            return

        for line in f:
            line_count += 1
            try:
                self._blocked_hosts |= self._read_hosts_line(line)
            except UnicodeDecodeError:
                logger.error("Failed to decode: {!r}".format(line))
                error_count += 1

        logger.debug("{}: read {} lines".format(byte_io.name, line_count))
        if error_count > 0:
            message.error(
                "hostblock: {} read errors for {}".format(error_count, byte_io.name)
            )

    def _on_lists_downloaded(self, done_count: int) -> None:
        """Install block lists after files have been downloaded."""
        try:
            with open(self._local_hosts_file, "w", encoding="utf-8") as f:
                for host in sorted(self._blocked_hosts):
                    f.write(host + "\n")
                message.info(
                    "hostblock: Read {} hosts from {} sources.".format(
                        len(self._blocked_hosts), done_count
                    )
                )
        except OSError:
            logger.exception("Failed to write host block list!")

    def update_files(self) -> None:
        """Update files when the config changed."""
        if not config.val.content.blocking.hosts.lists:
            try:
                os.remove(self._local_hosts_file)
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.exception("Failed to delete hosts file: {}".format(e))


@hook.config_changed("content.blocking.hosts.lists")
def on_lists_changed() -> None:
    host_blocker.update_files()


@hook.config_changed("content.blocking.method")
def on_method_changed() -> None:
    host_blocker.enabled = _should_be_used()


@hook.init()
def init(context: apitypes.InitContext) -> None:
    """Initialize the host blocker."""
    global host_blocker
    host_blocker = HostBlocker(
        data_dir=context.data_dir,
        config_dir=context.config_dir,
        has_basedir=context.args.basedir is not None,
    )
    host_blocker.read_hosts()
    interceptor.register(host_blocker.filter_request)
