#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Andy Mender <andymenderunix@gmail.com>

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

import sys
import argparse
import datetime
import os.path
import subprocess

import lxml.etree

import qutebrowser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils

# use basedir to get project root dir
appdata_path = os.path.join("misc", "org.qutebrowser.qutebrowser.appdata.xml")
version_xpath = '//*[@type="desktop"]/releases'


def bump_version(version_leap="patch"):
    """Update qutebrowser release version.

    Args:
        version_leap: define the jump between versions
        ("major", "minor", "patch")
    """
    subprocess.run([sys.executable, '-m', 'bumpversion', version_leap],
                   check=True)


def read_appdata():
    """Read qutebrowser.appdata.xml into an ElementTree object.

    :Return:
        ElementTree object representing appdata.xml
    """
    with open(appdata_path, "rb") as f:
        appdata = lxml.etree.fromstring(f.read())

    return appdata


def write_appdata(appdata):
    """Write qutebrowser.appdata ElementTree object to a file.

    Args:
        appdata: appdata ElementTree object
    """
    with open(appdata_path, "wb") as f:
        f.write(lxml.etree.tostring(appdata, pretty_print=True))


def add_release(releases, version_string, date_string):
    """Add new <release> block to <releases> block of the appdata XML.

    Args:
        releases: <releases> XML ElementTree
        version_string: new qutebrowser version
        date_string: release date for the new version
    """
    release = lxml.etree.Element("release")
    release.attrib["version"] = version_string
    release.attrib["date"] = date_string

    releases.append(release)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update release version.")
    parser.add_argument('bump', action="store",
                        choices=["major", "minor", "patch"],
                        help="Update release version")
    args = parser.parse_args()
    version = qutebrowser.__version__

    utils.change_cwd()
    bump_version(args.bump)

    appdata_tree = read_appdata()
    releases_block = appdata_tree.xpath(version_xpath)[0]
    add_release(releases_block, version, datetime.date.today().isoformat())
    write_appdata(appdata_tree)

    print("Run the following commands to create a new release:")
    print("* Run `git push origin; git push {v}`.".format(v=version))
    print("* If committing on minor branch, cherry-pick release commit to "
          "master.")
    print("* Create new release via GitHub (required to upload release "
          "artifacts).")
    print("* Linux: Run `git checkout {v} && "
          "./.venv/bin/python3 scripts/dev/build_release.py --upload`"
          .format(v=version))
    print("* Windows: Run `git checkout {v}; "
          "py -3 scripts\dev\\build_release.py --asciidoc "
          "C:\Python27\python "
          "%userprofile%\\bin\\asciidoc-8.6.10\\asciidoc.py --upload`."
          .format(v=version))
    print("* macOS: Run `git checkout {v} && "
          "python3 scripts/dev/build_release.py --upload`."
          .format(v=version))

    print("* On server:")
    print("- Run `python3 scripts/dev/download_release.py v{v}`."
          .format(v=version))
    print("- Run `git pull github master && sudo python3 "
          "scripts/asciidoc2html.py --website /srv/http/qutebrowser`")
