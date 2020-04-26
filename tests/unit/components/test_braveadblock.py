from PyQt5.QtCore import QUrl

import csv
import os.path
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
    )
]


def populate_blocker(blocker: BraveAdBlocker) -> None:
    for blocklist in ["easyprivacy.txt", "easylist.txt"]:
        blocklist_path = os.path.join(THIS_DIR, "data", blocklist)
        blocker._import_local(blocklist_path)


@pytest.fixture
def ad_blocker_factory(config_tmpdir, data_tmpdir, download_stub, config_stub):
    def factory():
        engine = Engine([])
        return BraveAdBlocker(engine=engine, data_dir=data_tmpdir)

    return factory


def test_dataset(ad_blocker_factory):
    """
    In the data folder, we have a file called `adblock_dataset.tsv`, which
    contains tuples of (url, source_url, type) in each line.

    Thus, this test is only meant to catch syntax errors and the like, not
    incorrectness in the adblocker. There are thus no assert statements.
    """
    def dataset_type_to_enum(type_int: int) -> ResourceType:
        """
        Translate
        """
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

    blocker = ad_blocker_factory()
    populate_blocker(blocker)

    dataset_path = os.path.join(THIS_DIR, "data", "adblock_dataset.tsv")
    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            url = QUrl(row["url"])
            source_url = QUrl(row["source_url"])
            resource_type = dataset_type_to_enum(int(row["type"]))
            blocker._is_blocked(url, source_url, resource_type)


def test_okay_urls(ad_blocker_factory):
    """Test if our set of okay are urls to check are blocked or not."""
    blocker = ad_blocker_factory()
    populate_blocker(blocker)

    for (str_url, source_str_url, request_type) in OKAY_URLS:
        url = QUrl(str_url)
        source_url = QUrl(source_str_url)
        assert not blocker._is_blocked(url, source_url, request_type)


def test_not_okay_urls(ad_blocker_factory):
    """Test if our set of not-okay are urls to check are blocked or not."""
    blocker = ad_blocker_factory()
    populate_blocker(blocker)

    for (str_url, source_str_url, request_type) in NOT_OKAY_URLS:
        url = QUrl(str_url)
        source_url = QUrl(source_str_url)
        assert blocker._is_blocked(url, source_url, request_type)
