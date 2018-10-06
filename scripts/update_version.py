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

from lxml import etree

# TODO: move to global constants?
appdata_path = "misc/qutebrowser.appdata.xml"
version_xpath = '//*[@type="desktop"]/releases'


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

    # read appdata XML
    appdata_tree = read_appdata()

    # get <releases> XML block
    releases = appdata_tree.xpath(version_xpath)[0]

    # attach example release
    add_release(releases, "1.5.0", "2018-10-06")

    # bump/add new version (from git tag?)
    for release in releases.iterchildren():
        print("version: {}, date: {}".format(release.get('version'),
                                             release.get('date')))

    # write appdata back to XML
    write_appdata(appdata_tree)
