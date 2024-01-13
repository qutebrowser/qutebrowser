#!/usr/bin/env python3

"""
Behavior:
    A qutebrowser userscript that creates bookmarks in Nextcloud's Bookmarks app.

Requirements:
    requests

userscript setup:
    Optionally create ~/.config/qutebrowser/add-nextcloud-bookmarks.ini like:

[nextcloud]
HOST=https://nextcloud.example.com
USER=username
;PASSWORD=lamepassword
DESCRIPTION=None
;TAGS=just-one
TAGS=read-me-later,added-by-qutebrowser, Another-One

    If settings aren't in the configuration file, the user will be prompted during
    bookmark creation.  If DESCRIPTION and TAGS are set to None, they will be left
    blank. If the user does not want to be prompted for a password, it is recommended
    to set up an 'app password'.  See the following for instructions:
    https://docs.nextcloud.com/server/latest/user_manual/en/session_management.html#managing-devices  # noqa: E501

qutebrowser setup:
    add bookmark via hints
        config.bind('X', 'hint links userscript add-nextcloud-bookmarks')

    add bookmark of current URL
        config.bind('X', 'spawn --userscript add-nextcloud-bookmarks')

troubleshooting:
    Errors detected within this userscript will have an exit of 231.  All other
    exit codes will come from requests.
"""

import configparser
from json import dumps
from os import environ, path
from sys import argv, exit

from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit
from requests import get, post
from requests.auth import HTTPBasicAuth


def get_text(name, info):
    """Get input from the user."""
    _app = QApplication(argv)  # noqa: F841
    if name == "password":
        text, ok = QInputDialog.getText(
            None,
            "add-nextcloud-bookmarks userscript",
            "Please enter {}".format(info),
            QLineEdit.EchoMode.Password,
        )
    else:
        text, ok = QInputDialog.getText(
            None, "add-nextcloud-bookmarks userscript", "Please enter {}".format(info)
        )
    if not ok:
        message("info", "Dialog box canceled.")
        exit(0)
    return text


def message(level, text):
    """display message"""
    with open(environ["QUTE_FIFO"], "w") as fifo:
        fifo.write(
            'message-{} "add-nextcloud-bookmarks userscript: {}"\n'.format(level, text)
        )
        fifo.flush()


if "QUTE_FIFO" not in environ:
    print(
        "This script is designed to run as a qutebrowser userscript, "
        "not as a standalone script."
    )
    exit(231)

if "QUTE_CONFIG_DIR" not in environ:
    if "XDG_CONFIG_HOME" in environ:
        QUTE_CONFIG_DIR = environ["XDG_CONFIG_HOME"] + "/qutebrowser"
    else:
        QUTE_CONFIG_DIR = environ["HOME"] + "/.config/qutebrowser"
else:
    QUTE_CONFIG_DIR = environ["QUTE_CONFIG_DIR"]

config_file = QUTE_CONFIG_DIR + "/add-nextcloud-bookmarks.ini"
if path.isfile(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    settings = dict(config.items("nextcloud"))
else:
    settings = {}

settings_info = [
    ("host", "host information.", "required"),
    ("user", "username.", "required"),
    ("password", "password.", "required"),
    ("description", "description or leave blank", "optional"),
    ("tags", "tags (comma separated) or leave blank", "optional"),
]

# check for settings that need user interaction and clear optional setting if need be
for setting in settings_info:
    if setting[0] not in settings:
        userInput = get_text(setting[0], setting[1])
        settings[setting[0]] = userInput
    if setting[2] == "optional":
        if settings[setting[0]] == "None":
            settings[setting[0]] = ""

tags = settings["tags"].split(",")

QUTE_URL = environ["QUTE_URL"]
api_url = settings["host"] + "/index.php/apps/bookmarks/public/rest/v2/bookmark"

auth = HTTPBasicAuth(settings["user"], settings["password"])
headers = {"Content-Type": "application/json"}
params = {"url": QUTE_URL}

# check if there is already a bookmark for the URL
r = get(
    api_url,
    auth=auth,
    headers=headers,
    params=params,
    timeout=(3.05, 27),
)
if r.status_code != 200:
    message(
        "error",
        "Could not connect to {} with status code {}".format(
            settings["host"], r.status_code
        ),
    )
    exit(r.status_code)

try:
    r.json()["data"][0]["id"]
except IndexError:
    pass
else:
    message("info", "bookmark already exists for {}".format(QUTE_URL))
    exit(0)

if environ["QUTE_MODE"] == "hints":
    QUTE_TITLE = QUTE_URL
else:
    QUTE_TITLE = environ["QUTE_TITLE"]

# JSON format
# https://nextcloud-bookmarks.readthedocs.io/en/latest/bookmark.html#create-a-bookmark
dict = {
    "url": QUTE_URL,
    "title": QUTE_TITLE,
    "description": settings["description"],
    "tags": tags,
}
data = dumps(dict)

r = post(api_url, data=data, headers=headers, auth=auth, timeout=(3.05, 27))

if r.status_code == 200:
    message("info", "bookmark {} added".format(QUTE_URL))
else:
    message("error", "something went wrong {} bookmark not added".format(QUTE_URL))
    exit(r.status_code)
