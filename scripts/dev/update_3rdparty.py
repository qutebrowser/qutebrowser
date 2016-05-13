#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Daniel Schadt
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

"""Update all third-party-modules."""

import argparse
import urllib.request
import urllib.error
import shutil
import json
import os


def get_latest_pdfjs_url():
    """Get the URL of the latest pdf.js prebuilt package.

    Returns a (version, url)-tuple.
    """
    github_api = 'https://api.github.com'
    endpoint = 'repos/mozilla/pdf.js/releases/latest'
    request_url = '{}/{}'.format(github_api, endpoint)
    with urllib.request.urlopen(request_url) as fp:
        data = json.loads(fp.read().decode('utf-8'))

    download_url = data['assets'][0]['browser_download_url']
    version_name = data['name']
    return (version_name, download_url)


def update_pdfjs(target_version=None):
    """Download and extract the latest pdf.js version.

    If target_version is not None, download the given version instead.

    Args:
        target_version: None or version string ('x.y.z')
    """
    if target_version is None:
        version, url = get_latest_pdfjs_url()
    else:
        # We need target_version as x.y.z, without the 'v' prefix, though the
        # user might give it on the command line
        if target_version.startswith('v'):
            target_version = target_version[1:]
        # version should have the prefix to be consistent with the return value
        # of get_latest_pdfjs_url()
        version = 'v' + target_version
        url = ('https://github.com/mozilla/pdf.js/releases/download/'
               'v{0}/pdfjs-{0}-dist.zip').format(target_version)

    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', '..'))
    target_path = os.path.join('qutebrowser', '3rdparty', 'pdfjs')
    print("=> Downloading pdf.js {}".format(version))
    try:
        (archive_path, _headers) = urllib.request.urlretrieve(url)
    except urllib.error.HTTPError as error:
        print("Could not retrieve pdfjs {}: {}".format(version, error))
        return
    if os.path.isdir(target_path):
        print("Removing old version in {}".format(target_path))
        shutil.rmtree(target_path)
    os.makedirs(target_path)
    print("Extracting new version")
    with open(archive_path, 'rb') as archive:
        shutil.unpack_archive(archive, target_path, 'zip')
    urllib.request.urlcleanup()


def update_dmg_makefile():
    """Update fancy-dmg Makefile.

    See https://el-tramo.be/blog/fancy-dmg/
    """
    print("Updating fancy-dmg Makefile...")
    url = 'https://raw.githubusercontent.com/remko/fancy-dmg/master/Makefile'
    target_path = os.path.join('scripts', 'dev', 'Makefile-dmg')
    urllib.request.urlretrieve(url, target_path)
    urllib.request.urlcleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--pdfjs', '-p',
        help='Specify pdfjs version. If not given, '
        'the latest version is used.',
        required=False, metavar='VERSION')
    parser.add_argument('--fancy-dmg', help="Update fancy-dmg Makefile",
                        action='store_true')
    args = parser.parse_args()

    update_pdfjs(args.pdfjs)
    if args.fancy_dmg:
        update_dmg_makefile()


if __name__ == '__main__':
    main()
