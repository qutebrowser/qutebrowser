# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
#!/usr/bin/env python3

# Copyright 2015 Corentin Julé <corentinjule@gmail.com>
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

import pathlib
import zipfile
import logging

import pytest

from PyQt5.QtCore import QUrl

from qutebrowser.components import hostblock
from qutebrowser.utils import urlmatch
from helpers import testutils


pytestmark = pytest.mark.usefixtures("qapp")

# TODO See ../utils/test_standarddirutils for OSError and caplog assertion

WHITELISTED_HOSTS = ("qutebrowser.org", "mediumhost.io", "http://*.edu")

BLOCKLIST_HOSTS = (
    "localhost",
    "mediumhost.io",
    "malware.badhost.org",
    "4-verybadhost.com",
    "ads.worsthostever.net",
)

CLEAN_HOSTS = ("goodhost.gov", "verygoodhost.com")

URLS_TO_CHECK = (
    "http://localhost",
    "http://mediumhost.io",
    "ftp://malware.badhost.org",
    "http://4-verybadhost.com",
    "http://ads.worsthostever.net",
    "http://goodhost.gov",
    "ftp://verygoodhost.com",
    "http://qutebrowser.org",
    "http://veryverygoodhost.edu",
)


@pytest.fixture
def host_blocker_factory(config_tmpdir, data_tmpdir, download_stub, config_stub):
    def factory():
        return hostblock.HostBlocker(config_dir=config_tmpdir, data_dir=data_tmpdir)

    return factory


def create_zipfile(directory, files, zipname="test"):
    """Return a path to a newly created zip file.

    Args:
        directory: path object where to create the zip file.
        files: list of pathlib.Paths (relative to directory) to each file to add.
        zipname: name to give to the zip file.
    """
    zipfile_path = (directory / zipname).with_suffix(".zip")
    with zipfile.ZipFile(zipfile_path, "w") as new_zipfile:
        for file_path in files:
            new_zipfile.write(directory / file_path, arcname=file_path.name)
            # Removes path from file name
    return pathlib.Path(zipname + ".zip")


def create_blocklist(
    directory, blocked_hosts=BLOCKLIST_HOSTS, name="hosts", line_format="one_per_line"
):
    """Return a path to a blocklist file.

    Args:
        directory: path object where to create the blocklist file
        blocked_hosts: an iterable of string hosts to add to the blocklist
        name: name to give to the blocklist file
        line_format: 'etc_hosts'  -->  /etc/hosts format
                    'one_per_line'  -->  one host per line format
                    'not_correct'  -->  Not a correct hosts file format.
    """
    blocklist_file = directory / name
    with blocklist_file.open("w", encoding="UTF-8") as blocklist:
        # ensure comments are ignored when processing blocklist
        blocklist.write("# Blocked Hosts List #\n\n")
        if line_format == "etc_hosts":  # /etc/hosts like format
            for host in blocked_hosts:
                blocklist.write("127.0.0.1  " + host + "\n")
        elif line_format == "one_per_line":
            for host in blocked_hosts:
                blocklist.write(host + "\n")
        elif line_format == "not_correct":
            for host in blocked_hosts:
                blocklist.write(host + " This is not a correct hosts file\n")
        else:
            raise ValueError("Incorrect line_format argument")
    return pathlib.Path(name)


def assert_urls(
    host_blocker,
    blocked=BLOCKLIST_HOSTS,
    whitelisted=WHITELISTED_HOSTS,
    urls_to_check=URLS_TO_CHECK,
):
    """Test if Urls to check are blocked or not by HostBlocker.

    Ensure URLs in 'blocked' and not in 'whitelisted' are blocked.
    All other URLs must not be blocked.

    localhost is an example of a special case that shouldn't be blocked.
    """
    whitelisted = list(whitelisted) + ["localhost"]
    for str_url in urls_to_check:
        url = QUrl(str_url)
        host = url.host()
        if host in blocked and host not in whitelisted:
            assert host_blocker._is_blocked(url)
        else:
            assert not host_blocker._is_blocked(url)


def blocklist_to_url(path):
    """Get an example.com-URL with the given filename as path."""
    assert not path.is_absolute(), path
    url = QUrl("http://example.com/")
    url.setPath("/" + str(path))
    assert url.isValid(), url.errorString()
    return url


def generic_blocklists(directory):
    """Return a generic list of files to be used in hosts-block-lists option.

    This list contains :
    - a remote zip file with 1 hosts file and 2 useless files
    - a remote zip file with only useless files
        (Should raise a FileNotFoundError)
    - a remote zip file with only one valid hosts file
    - a local text file with valid hosts
    - a remote text file without valid hosts format.
    """
    # remote zip file with 1 hosts file and 2 useless files
    file1 = create_blocklist(
        directory, blocked_hosts=CLEAN_HOSTS, name="README", line_format="not_correct"
    )
    file2 = create_blocklist(
        directory,
        blocked_hosts=BLOCKLIST_HOSTS[:3],
        name="hosts",
        line_format="etc_hosts",
    )
    file3 = create_blocklist(
        directory,
        blocked_hosts=CLEAN_HOSTS,
        name="false_positive",
        line_format="one_per_line",
    )
    files_to_zip = [file1, file2, file3]
    blocklist1 = blocklist_to_url(create_zipfile(directory, files_to_zip, "block1"))

    # remote zip file without file named hosts
    # (Should raise a FileNotFoundError)
    file1 = create_blocklist(
        directory, blocked_hosts=CLEAN_HOSTS, name="md5sum", line_format="etc_hosts"
    )
    file2 = create_blocklist(
        directory, blocked_hosts=CLEAN_HOSTS, name="README", line_format="not_correct"
    )
    file3 = create_blocklist(
        directory,
        blocked_hosts=CLEAN_HOSTS,
        name="false_positive",
        line_format="one_per_line",
    )
    files_to_zip = [file1, file2, file3]
    blocklist2 = blocklist_to_url(create_zipfile(directory, files_to_zip, "block2"))

    # remote zip file with only one valid hosts file inside
    file1 = create_blocklist(
        directory,
        blocked_hosts=[BLOCKLIST_HOSTS[3]],
        name="malwarelist",
        line_format="etc_hosts",
    )
    blocklist3 = blocklist_to_url(create_zipfile(directory, [file1], "block3"))

    # local text file with valid hosts
    blocklist4 = QUrl.fromLocalFile(
        str(
            directory
            / create_blocklist(
                directory,
                blocked_hosts=[BLOCKLIST_HOSTS[4]],
                name="mycustomblocklist",
                line_format="one_per_line",
            )
        )
    )
    assert blocklist4.isValid(), blocklist4.errorString()

    # remote text file without valid hosts format
    blocklist5 = blocklist_to_url(
        create_blocklist(
            directory,
            blocked_hosts=CLEAN_HOSTS,
            name="notcorrectlist",
            line_format="not_correct",
        )
    )

    return [
        blocklist1.toString(),
        blocklist2.toString(),
        blocklist3.toString(),
        blocklist4.toString(),
        blocklist5.toString(),
    ]


@pytest.mark.parametrize(
    "blocking_enabled, method",
    [
        # Assuming the adblock dependency is installed
        (True, "auto"),
        (True, "adblock"),
        (False, "auto"),
        (False, "adblock"),
        (False, "both"),
        (False, "hosts"),
    ],
)
def test_disabled_blocking_update(
    config_stub, tmp_path, caplog, host_blocker_factory, blocking_enabled, method
):
    """Ensure no URL is blocked when host blocking should be disabled."""
    if blocking_enabled and method == 'auto':
        pytest.importorskip('adblock')

    config_stub.val.content.blocking.hosts.lists = generic_blocklists(tmp_path)
    config_stub.val.content.blocking.enabled = blocking_enabled
    config_stub.val.content.blocking.method = method

    host_blocker = host_blocker_factory()
    downloads = host_blocker.adblock_update()
    while downloads._in_progress:
        current_download = downloads._in_progress[0]
        with caplog.at_level(logging.ERROR):
            current_download.successful = True
            current_download.finished.emit()
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker._is_blocked(QUrl(str_url))


def test_disabled_blocking_per_url(config_stub, host_blocker_factory):
    example_com = "https://www.example.com/"

    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.hosts.lists = []
    pattern = urlmatch.UrlPattern(example_com)
    config_stub.set_obj("content.blocking.enabled", False, pattern=pattern)

    url = QUrl("blocked.example.com")

    host_blocker = host_blocker_factory()
    host_blocker._blocked_hosts.add(url.host())

    assert host_blocker._is_blocked(url)
    assert not host_blocker._is_blocked(url, first_party_url=QUrl(example_com))


def test_no_blocklist_update(config_stub, download_stub, host_blocker_factory):
    """Ensure no URL is blocked when no block list exists."""
    config_stub.val.content.blocking.hosts.lists = None
    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.enabled = True

    host_blocker = host_blocker_factory()
    host_blocker.adblock_update()
    host_blocker.read_hosts()
    for dl in download_stub.downloads:
        dl.successful = True
    for str_url in URLS_TO_CHECK:
        assert not host_blocker._is_blocked(QUrl(str_url))


def test_successful_update(config_stub, tmp_path, caplog, host_blocker_factory):
    """Ensure hosts from host_blocking.lists are blocked after an update."""
    config_stub.val.content.blocking.hosts.lists = generic_blocklists(tmp_path)
    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.enabled = True
    config_stub.val.content.blocking.whitelist = None

    host_blocker = host_blocker_factory()
    downloads = host_blocker.adblock_update()
    # Simulate download is finished
    while downloads._in_progress:
        current_download = downloads._in_progress[0]
        with caplog.at_level(logging.ERROR):
            current_download.successful = True
            current_download.finished.emit()
    host_blocker.read_hosts()
    assert_urls(host_blocker, whitelisted=[])


def test_parsing_multiple_hosts_on_line(config_stub, host_blocker_factory):
    """Ensure multiple hosts on a line get parsed correctly."""
    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.enabled = True

    host_blocker = host_blocker_factory()
    bytes_host_line = " ".join(BLOCKLIST_HOSTS).encode("utf-8")
    parsed_hosts = host_blocker._read_hosts_line(bytes_host_line)
    host_blocker._blocked_hosts |= parsed_hosts
    assert_urls(host_blocker, whitelisted=[])


@pytest.mark.parametrize(
    "ip, host",
    [
        ("127.0.0.1", "localhost"),
        ("27.0.0.1", "localhost.localdomain"),
        ("27.0.0.1", "local"),
        ("55.255.255.255", "broadcasthost"),
        (":1", "localhost"),
        (":1", "ip6-localhost"),
        (":1", "ip6-loopback"),
        ("e80::1%lo0", "localhost"),
        ("f00::0", "ip6-localnet"),
        ("f00::0", "ip6-mcastprefix"),
        ("f02::1", "ip6-allnodes"),
        ("f02::2", "ip6-allrouters"),
        ("ff02::3", "ip6-allhosts"),
        (".0.0.0", "0.0.0.0"),
        ("127.0.1.1", "myhostname"),
        ("127.0.0.53", "myhostname"),
    ],
)
def test_whitelisted_lines(host_blocker_factory, ip, host):
    """Make sure we don't block hosts we don't want to."""
    host_blocker = host_blocker_factory()
    line = ("{} {}".format(ip, host)).encode("ascii")
    parsed_hosts = host_blocker._read_hosts_line(line)
    assert host not in parsed_hosts


def test_failed_dl_update(config_stub, tmp_path, caplog, host_blocker_factory):
    """One blocklist fails to download.

    Ensure hosts from this list are not blocked.
    """
    dl_fail_blocklist = blocklist_to_url(
        create_blocklist(
            tmp_path,
            blocked_hosts=CLEAN_HOSTS,
            name="download_will_fail",
            line_format="one_per_line",
        )
    )
    hosts_to_block = generic_blocklists(tmp_path) + [dl_fail_blocklist.toString()]
    config_stub.val.content.blocking.hosts.lists = hosts_to_block
    config_stub.val.content.blocking.enabled = True
    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.whitelist = None

    host_blocker = host_blocker_factory()
    downloads = host_blocker.adblock_update()
    while downloads._in_progress:
        current_download = downloads._in_progress[0]
        # if current download is the file we want to fail, make it fail
        if current_download.name == dl_fail_blocklist.path():
            current_download.successful = False
        else:
            current_download.successful = True
        with caplog.at_level(logging.ERROR):
            current_download.finished.emit()
    host_blocker.read_hosts()
    assert_urls(host_blocker, whitelisted=[])


@pytest.mark.parametrize("location", ["content", "comment"])
def test_invalid_utf8(config_stub, tmp_path, caplog, host_blocker_factory, location):
    """Make sure invalid UTF-8 is handled correctly.

    See https://github.com/qutebrowser/qutebrowser/issues/2301
    """
    blocklist = tmp_path / "blocklist"
    if location == "comment":
        blocklist.write_bytes(b"# nbsp: \xa0\n")
    else:
        assert location == "content"
        blocklist.write_bytes(b"https://www.example.org/\xa0")
    with blocklist.open("a") as f:
        for url in BLOCKLIST_HOSTS:
            f.write(url + "\n")

    url = blocklist_to_url(pathlib.Path("blocklist"))
    config_stub.val.content.blocking.hosts.lists = [url.toString()]
    config_stub.val.content.blocking.enabled = True
    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.whitelist = None

    host_blocker = host_blocker_factory()
    downloads = host_blocker.adblock_update()
    current_download = downloads._in_progress[0]

    if location == "content":
        with caplog.at_level(logging.ERROR):
            current_download.successful = True
            current_download.finished.emit()
        expected = r"Failed to decode: " r"b'https://www.example.org/\xa0localhost"
        assert caplog.messages[-2].startswith(expected)
    else:
        current_download.successful = True
        current_download.finished.emit()

    host_blocker.read_hosts()
    assert_urls(host_blocker, whitelisted=[])


def test_invalid_utf8_compiled(
    config_stub, config_tmpdir, data_tmpdir, monkeypatch, caplog, host_blocker_factory
):
    """Make sure invalid UTF-8 in the compiled file is handled."""
    config_stub.val.content.blocking.hosts.lists = []

    # Make sure the HostBlocker doesn't delete blocked-hosts in __init__
    monkeypatch.setattr(hostblock.HostBlocker, "update_files", lambda _self: None)

    (config_tmpdir / "blocked-hosts").write_binary(b"https://www.example.org/\xa0")
    (data_tmpdir / "blocked-hosts").ensure()

    host_blocker = host_blocker_factory()
    with caplog.at_level(logging.ERROR):
        host_blocker.read_hosts()
    assert caplog.messages[-1] == "Failed to read host blocklist!"


def test_blocking_with_whitelist(config_stub, data_tmpdir, host_blocker_factory):
    """Ensure hosts in content.blocking.whitelist are never blocked."""
    # Simulate adblock_update has already been run
    # by creating a file named blocked-hosts,
    # Exclude localhost from it as localhost is never blocked via list
    filtered_blocked_hosts = BLOCKLIST_HOSTS[1:]
    blocklist = create_blocklist(
        data_tmpdir,
        blocked_hosts=filtered_blocked_hosts,
        name="blocked-hosts",
        line_format="one_per_line",
    )
    config_stub.val.content.blocking.hosts.lists = [str(blocklist)]
    config_stub.val.content.blocking.enabled = True
    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.whitelist = list(WHITELISTED_HOSTS)

    host_blocker = host_blocker_factory()
    host_blocker.read_hosts()
    assert_urls(host_blocker)


def test_config_change_initial(config_stub, tmp_path, host_blocker_factory):
    """Test emptying host_blocking.lists with existing blocked_hosts.

    - A blocklist is present in host_blocking.lists and blocked_hosts is
      populated
    - User quits qutebrowser, empties host_blocking.lists from his config
    - User restarts qutebrowser, does adblock-update
    """
    create_blocklist(
        tmp_path,
        blocked_hosts=BLOCKLIST_HOSTS,
        name="blocked-hosts",
        line_format="one_per_line",
    )
    config_stub.val.content.blocking.hosts.lists = None
    config_stub.val.content.blocking.enabled = True
    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.whitelist = None

    host_blocker = host_blocker_factory()
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker._is_blocked(QUrl(str_url))


def test_config_change(config_stub, tmp_path, host_blocker_factory):
    """Ensure blocked-hosts resets if host-block-list is changed to None."""
    filtered_blocked_hosts = BLOCKLIST_HOSTS[1:]  # Exclude localhost
    blocklist = blocklist_to_url(
        create_blocklist(
            tmp_path,
            blocked_hosts=filtered_blocked_hosts,
            name="blocked-hosts",
            line_format="one_per_line",
        )
    )
    config_stub.val.content.blocking.hosts.lists = [blocklist.toString()]
    config_stub.val.content.blocking.enabled = True
    config_stub.val.content.blocking.method = "hosts"
    config_stub.val.content.blocking.whitelist = None

    host_blocker = host_blocker_factory()
    host_blocker.read_hosts()
    config_stub.val.content.blocking.hosts.lists = None
    host_blocker.read_hosts()
    for str_url in URLS_TO_CHECK:
        assert not host_blocker._is_blocked(QUrl(str_url))


def test_add_directory(config_stub, tmp_path, host_blocker_factory):
    """Ensure adblocker can import all files in a directory."""
    blocklist_hosts2 = []
    for i in BLOCKLIST_HOSTS[1:]:
        blocklist_hosts2.append("1" + i)

    create_blocklist(
        tmp_path,
        blocked_hosts=BLOCKLIST_HOSTS,
        name="blocked-hosts",
        line_format="one_per_line",
    )
    create_blocklist(
        tmp_path,
        blocked_hosts=blocklist_hosts2,
        name="blocked-hosts2",
        line_format="one_per_line",
    )

    config_stub.val.content.blocking.hosts.lists = [str(tmp_path)]
    config_stub.val.content.blocking.enabled = True
    config_stub.val.content.blocking.method = "hosts"
    host_blocker = host_blocker_factory()
    host_blocker.adblock_update()
    assert len(host_blocker._blocked_hosts) == len(blocklist_hosts2) * 2


def test_adblock_benchmark(data_tmpdir, benchmark, host_blocker_factory):
    blocked_hosts = data_tmpdir / "blocked-hosts"
    blocked_hosts.write_text("\n".join(testutils.blocked_hosts()), encoding="utf-8")

    url = QUrl("https://www.example.org/")
    blocker = host_blocker_factory()
    blocker.read_hosts()
    assert blocker._blocked_hosts

    benchmark(lambda: blocker._is_blocked(url))
