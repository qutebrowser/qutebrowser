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
from datetime import date
import subprocess

from lxml import etree

# TODO: move to global constants?
appdata_path = "misc/qutebrowser.appdata.xml"
version_xpath = '//*[@type="desktop"]/releases'


def bump_version(version_leap = "patch"):
    """Update qutebrowser release version in .bumpversion.cfg

    :param version_leap: define the jump between versions ("major", "minor", "patch")
    """


    # NOTE: this may rely on the python version used to launch the function
    # and whether the wrapper script 'bumpversion' was provided
    subprocess.run(['bump2version', version_leap, '--allow-dirty'])


def read_appdata():
    """Reads the appdata XML into an ElementTree object

    :return: ElementTree object
    """

    with open(appdata_path, "rb") as f:
        appdata_tree = etree.fromstring(f.read())

    return appdata_tree


def write_appdata(appdata_tree):
    """Write appdata tree object back to XML file

    :param appdata_tree: appdata ElementTree object
    """

    with open(appdata_path, "wb") as f:
        f.write(etree.tostring(appdata_tree, pretty_print=True))


def add_release(releases, version_string, date_string):
    """Add new <release> block to <releases> block of the appdata XML

    :param releases: <releases> XML ElementTree
    :param version_string: new qutebrowser version
    :param date_string: release date for the new version
    :return:
    """

    # create <release> block and populate
    release = etree.Element("release")
    release.attrib["version"] = version_string
    release.attrib["date"] = date_string

    # attach new release to <releases> block
    releases.append(release)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update release version and appdata.xml")
    parser.add_argument('bump', action="store", choices=["major", "minor", "patch"],
                        required=False, help="Update release version")
    args = parser.parse_args()

    # bump version globally
    if args.bump is not None:
        bump_version(args.bump)

        # NOTE: this step must be executed AFTER bumping the version!
        from qutebrowser import __version__

        # read appdata XML
        appdata_tree = read_appdata()

        # get <releases> XML block
        releases = appdata_tree.xpath(version_xpath)[0]

        # attach new release
        # TODO: use different date string?
        add_release(releases, __version__, date.today().isoformat())

        # write appdata back to XML
        write_appdata(appdata_tree)
    else:
        print("Option 'bump' not specified via command-line. Nothing was changed.")
