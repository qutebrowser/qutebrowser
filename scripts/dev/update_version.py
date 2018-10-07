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

import argparse
import datetime
import os.path
import subprocess

from lxml import etree

from qutebrowser import basedir

# use basedir to get project root dir
appdata_path = os.path.join(os.path.dirname(basedir), "misc",
                            "qutebrowser.appdata.xml")
version_xpath = '//*[@type="desktop"]/releases'


def bump_version(version_leap="patch"):
    """Update qutebrowser release version.

    Args:
        version_leap: define the jump between versions
        ("major", "minor", "patch")
    """
    subprocess.run(['bump2version', version_leap], check=True)


def read_appdata():
    """Read qutebrowser.appdata.xml into an ElementTree object.

    :Return:
        ElementTree object representing appdata.xml
    """
    with open(appdata_path, "rb") as f:
        appdata = etree.fromstring(f.read())

    return appdata


def write_appdata(appdata):
    """Write qutebrowser.appdata ElementTree object to a file.

    Args:
        appdata: appdata ElementTree object
    """
    with open(appdata_path, "wb") as f:
        f.write(etree.tostring(appdata, pretty_print=True))


def add_release(releases, version_string, date_string):
    """Add new <release> block to <releases> block of the appdata XML.

    Args:
        releases: <releases> XML ElementTree
        version_string: new qutebrowser version
        date_string: release date for the new version
    """
    release = etree.Element("release")
    release.attrib["version"] = version_string
    release.attrib["date"] = date_string

    releases.append(release)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update release version.")
    parser.add_argument('bump', action="store",
                        choices=["major", "minor", "patch"],
                        required=False, help="Update release version")
    args = parser.parse_args()

    # bump version globally
    if args.bump is not None:
        bump_version(args.bump)

        from qutebrowser import __version__

        appdata_tree = read_appdata()

        releases_block = appdata_tree.xpath(version_xpath)[0]

        add_release(releases_block, __version__,
                    datetime.date.today().isoformat())

        write_appdata(appdata_tree)
    else:
        print("Option 'bump' not specified via command-line."
              " Nothing was changed.")
