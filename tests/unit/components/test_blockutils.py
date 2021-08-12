# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
#!/usr/bin/env python3

# Copyright 2020-2021 Árni Dagur <arni@dagur.eu>
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

import io
from typing import IO

from PyQt5.QtCore import QUrl

import pytest

from qutebrowser.components.utils import blockutils


@pytest.fixture
def pretend_blocklists(tmp_path):
    """Put fake blocklists into a tempdir.

    Put fake blocklists blocklists into a temporary directory, then return
    both a list containing `file://` urls, and the residing dir.
    """
    data = [
        (["cdn.malwarecorp.is", "evil-industries.com"], "malicious-hosts.txt"),
        (["news.moms-against-icecream.net"], "blocklist.list"),
    ]
    # Add a bunch of automatically generated blocklist as well
    for n in range(8):
        data.append(([f"example{n}.com", f"example{n+1}.net"], f"blocklist{n}"))

    bl_dst_dir = tmp_path / "blocklists"
    bl_dst_dir.mkdir()
    urls = []
    for blocklist_lines, filename in data:
        bl_dst_path = bl_dst_dir / filename
        bl_dst_path.write_text("\n".join(blocklist_lines), encoding="utf-8")
        assert bl_dst_path.is_file()
        urls.append(QUrl.fromLocalFile(str(bl_dst_path)).toString())
    return urls, bl_dst_dir


def test_blocklist_dl(qtbot, pretend_blocklists):
    total_expected = 10
    num_single_dl_called = 0

    def on_single_download(download: IO[bytes]) -> None:
        nonlocal num_single_dl_called
        num_single_dl_called += 1

        num_lines = 0
        with io.TextIOWrapper(download, encoding="utf-8") as dl_io:
            for line in dl_io:
                assert line.split(".")[-1].strip() in ("com", "net", "is")
                num_lines += 1
        assert num_lines >= 1

    list_qurls = [QUrl(blocklist) for blocklist in pretend_blocklists[0]]

    dl = blockutils.BlocklistDownloads(list_qurls)
    dl.single_download_finished.connect(on_single_download)

    with qtbot.wait_signal(dl.all_downloads_finished) as blocker:
        dl.initiate()
        assert blocker.args == [total_expected]

    assert num_single_dl_called == total_expected
