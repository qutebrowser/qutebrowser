# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

import logging
import csv
import os.path
from typing import Tuple, List
from shutil import copy

from PyQt5.QtCore import QUrl

import pytest
from adblock import Engine

from qutebrowser.api.interceptor import ResourceType
from qutebrowser.components.braveadblock import BraveAdBlocker

pytestmark = pytest.mark.usefixtures("qapp")

THIS_DIR = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

OKAY_URLS = [
    (
        "https://qutebrowser.org/icons/qutebrowser.svg",
        "https://qutebrowser.org",
        ResourceType.image,
    ),
    (
        "https://qutebrowser.org/doc/img/main.png",
        "https://qutebrowser.org",
        ResourceType.image,
    ),
    (
        "https://qutebrowser.org/media/font.css",
        "https://qutebrowser.org",
        ResourceType.stylesheet,
    ),
    (
        "https://www.ruv.is/sites/default/files/styles/2000x1125/public/fr_20180719_091367_1.jpg?itok=0zTNSKKS&timestamp=1561275315",
        "https://www.ruv.is/frett/2020/04/23/today-is-the-first-day-of-summer",
        ResourceType.image,
    ),
]

NOT_OKAY_URLS = [
    (
        "https://pagead2.googlesyndication.com/pcs/activeview?xai=AKAOjsvBN5MuZsVQyE7HD18bD-JjK589TD3zkugwCoLE2C5nP26WFNCQb8WwxzZTelPEHwwnhaOCsGxYc8WeFgYZLReqLYl8r9BtAQ6r83OHa04&sig=Cg0ArKJSzKMgXuVbXAD1EAE&adk=1473563476&tt=-1&bs=1431%2C473&mtos=120250,120250,120250,120250,120250&tos=120250,0,0,0,0&p=60,352,150,1080&mcvt=120250&rs=0&ht=0&tfs=5491&tls=125682&mc=1&lte=0&bas=0&bac=0&if=1&met=ie&avms=nio&exg=1&md=2&btr=0&lm=2&rst=1587887205533&dlt=226&rpt=1849&isd=0&msd=0&ext&xdi=0&ps=1431%2C7860&ss=1440%2C810&pt=-1&bin=4&deb=1-0-0-1192-5-1191-1191-0-0-0&tvt=125678&is=728%2C90&iframe_loc=https%3A%2F%2Ftpc.googlesyndication.com%2Fsafeframe%2F1-0-37%2Fhtml%2Fcontainer.html&r=u&id=osdtos&vs=4&uc=1192&upc=1&tgt=DIV&cl=1&cec=1&wf=0&cac=1&cd=0x0&itpl=19&v=20200422",
        "https://google.com",
        ResourceType.image,
    ),
    (
        "https://e.deployads.com/e/myanimelist.net",
        "https://myanimelist.net",
        ResourceType.xhr,
    ),
    (
        "https://c.amazon-adsystem.com/aax2/apstag.js",
        "https://www.reddit.com",
        ResourceType.script,
    ),
    (
        "https://c.aaxads.com/aax.js?pub=AAX763KC6&hst=www.reddit.com&ver=1.2",
        "https://www.reddit.com",
        ResourceType.script,
    ),
    (
        "https://pixel.mathtag.com/sync/img/?mt_exid=10009&mt_exuid=&mm_bnc&mm_bct&UUID=c7b65ea6-76cc-4700-b0c7-6dbcd10820ed",
        "https://damndelicious.net/2019/04/03/easy-slow-cooker-chili/",
        ResourceType.image,
    ),
]


def create_blocklist_invalid_utf8(directory) -> str:
    dest_path = os.path.join(directory, "invalid_utf8.txt")
    with open(dest_path, "wb") as f:
        f.write(b"invalidutf8\xa0")
    return QUrl.fromLocalFile(dest_path).toString()


def create_easylist_easyprivacy(directory) -> List[str]:
    """Copy the easyprivacy and easylist blocklists into the given dir."""
    urls = []
    for blocklist in ["easyprivacy.txt", "easylist.txt"]:
        bl_src_path = os.path.join(THIS_DIR, "data", blocklist)
        bl_dst_path = os.path.join(directory, blocklist)
        assert not os.path.isfile(bl_dst_path)
        copy(bl_src_path, bl_dst_path)
        assert os.path.isfile(bl_dst_path)
        urls.append(QUrl.fromLocalFile(bl_dst_path).toString())
    return urls


@pytest.fixture
def ad_blocker_factory(config_tmpdir, data_tmpdir, download_stub, config_stub):
    def factory():
        engine = Engine([])
        return BraveAdBlocker(engine=engine, data_dir=data_tmpdir)

    return factory


def assert_urls(
    ad_blocker: BraveAdBlocker,
    urls: Tuple[str, str, ResourceType],
    should_be_blocked: bool,
) -> None:
    for (str_url, source_str_url, request_type) in urls:
        url = QUrl(str_url)
        source_url = QUrl(source_str_url)
        if should_be_blocked:
            assert ad_blocker._is_blocked(url, source_url, request_type)
        else:
            assert not ad_blocker._is_blocked(url, source_url, request_type)


@pytest.mark.parametrize(
    "blocking_enabled, should_be_blocked", [(True, True), (False, False)]
)
def test_blocking_enabled(
    config_stub, tmpdir, caplog, ad_blocker_factory, blocking_enabled, should_be_blocked
):
    """Tests that the ads are blocked when the adblocker is enabled, and vice versa."""
    config_stub.val.content.ad_blocking.lists = create_easylist_easyprivacy(tmpdir)
    config_stub.val.content.ad_blocking.enabled = blocking_enabled

    ad_blocker = ad_blocker_factory()
    ad_blocker.adblock_update()
    while ad_blocker._in_progress:
        current_download = ad_blocker._in_progress[0]
        with caplog.at_level(logging.ERROR):
            current_download.successful = True
            current_download.finished.emit()
    assert_urls(ad_blocker, NOT_OKAY_URLS, should_be_blocked)


def test_invalid_utf8(ad_blocker_factory, config_stub, tmpdir, caplog):
    """Test that the adblocker handles invalid utf-8 correctly."""
    config_stub.val.content.ad_blocking.lists = [create_blocklist_invalid_utf8(tmpdir)]
    config_stub.val.content.ad_blocking.enabled = True

    ad_blocker = ad_blocker_factory()
    with caplog.at_level(logging.INFO):
        ad_blocker.adblock_update()
    expected = "Block list is not valid utf-8"
    assert caplog.messages[-2].startswith(expected)


def test_dataset(ad_blocker_factory, tmpdir, config_stub):
    """Run the ad-blocking logic on a bunch of urls.

    In the data folder, we have a file called `adblock_dataset.tsv`, which
    contains tuples of (url, source_url, type) in each line. We run these
    through the ad blocker to see if we get any exceptions.

    This test is only meant to catch syntax errors and the like, not
    incorrectness in the adblocker. There are thus no assert statements.
    """

    def dataset_type_to_enum(type_int: int) -> ResourceType:
        """Translate the dataset's encoding of a resource type to Qutebrowser's."""
        if type_int == 0:
            return ResourceType.unknown
        elif type_int == 1:
            return ResourceType.image
        elif type_int == 2:
            return ResourceType.stylesheet
        elif type_int == 3:
            return ResourceType.media
        elif type_int == 4:
            return ResourceType.script
        elif type_int == 5:
            return ResourceType.font_resource
        elif type_int == 6:
            return ResourceType.xhr
        else:
            assert type_int == 7
            return ResourceType.sub_frame

    config_stub.val.content.ad_blocking.lists = create_easylist_easyprivacy(tmpdir)
    config_stub.val.content.ad_blocking.enabled = True

    blocker = ad_blocker_factory()
    blocker.adblock_update()

    dataset_path = os.path.join(THIS_DIR, "data", "adblock_dataset.tsv")
    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            url = QUrl(row["url"])
            source_url = QUrl(row["source_url"])
            resource_type = dataset_type_to_enum(int(row["type"]))
            blocker._is_blocked(url, source_url, resource_type)
