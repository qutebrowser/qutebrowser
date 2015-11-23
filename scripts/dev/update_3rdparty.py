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

import urllib.request
import tempfile
import shutil
import json
import os


def get_latest_pdfjs_url():
    """Get the URL of the latest pdf.js prebuilt package.

    Returns a (version, url)-tuple."""
    github_api = 'https://api.github.com'
    endpoint = 'repos/mozilla/pdf.js/releases/latest'
    request_url = '{}/{}'.format(github_api, endpoint)
    with urllib.request.urlopen(request_url) as fp:
        data = json.loads(fp.read().decode('utf-8'))

    download_url = data['assets'][0]['browser_download_url']
    version_name = data['name']
    return (version_name, download_url)


def update_pdfjs():
    version, url = get_latest_pdfjs_url()
    target_path = os.path.join('qutebrowser', '3rdparty', 'pdfjs')
    print("=> Downloading pdf.js {}".format(version))
    with tempfile.NamedTemporaryFile(prefix='qute-pdfjs-') as archive:
        urllib.request.urlretrieve(url, archive.name)
        if os.path.isdir(target_path):
            print("Removing old version in {}".format(target_path))
            shutil.rmtree(target_path)
        os.makedirs(target_path)
        print("Extracting new version")
        shutil.unpack_archive(archive, target_path, 'zip')




def main():
    update_pdfjs()

if __name__ == '__main__':
    main()
