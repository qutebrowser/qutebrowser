#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Update all third-party-modules."""

import argparse
import urllib.request
import urllib.error
import shutil
import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
from scripts import dictcli
from qutebrowser.config import configdata


def download_nsis_plugins():
    """Download the plugins required by the NSIS script."""
    github_url = 'https://raw.githubusercontent.com/Drizin/NsisMultiUser'
    git_commit = 'master'
    nsh_files = ('Include/NsisMultiUser.nsh', 'Include/NsisMultiUserLang.nsh',
                 'Include/UAC.nsh', 'Include/StdUtils.nsh',
                 'Demos/Common/Utils.nsh')
    dll_files = ('Plugins/x86-unicode/UAC.dll',
                 'Plugins/x86-unicode/StdUtils.dll')
    include_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', '..', 'misc', 'nsis',
                               'include')
    plugins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', '..', 'misc', 'nsis',
                               'plugins', 'x86-unicode')
    os.makedirs(include_dir, exist_ok=True)
    os.makedirs(plugins_dir, exist_ok=True)
    print("=> Downloading NSIS plugins")
    for nsh_file in nsh_files:
        target_path = os.path.join(include_dir, os.path.basename(nsh_file))
        urllib.request.urlretrieve('{}/{}/{}'.format(github_url, git_commit,
                                                     nsh_file), target_path)
    for dll_file in dll_files:
        target_path = os.path.join(plugins_dir, os.path.basename(dll_file))
        urllib.request.urlretrieve('{}/{}/{}'.format(github_url, git_commit,
                                                     dll_file), target_path)
    urllib.request.urlcleanup()


def find_pdfjs_asset(assets, legacy):
    """Find the PDF.js asset to use."""
    for asset in assets:
        name = asset["name"]
        if (
            name.startswith("pdfjs-") and
            name.endswith("-dist.zip") and
            name.endswith("-legacy-dist.zip") == legacy
        ):
            return asset
    raise Exception(f"No pdfjs found in {assets}")


def get_latest_pdfjs_url(gh_token, legacy):
    """Get the URL of the latest pdf.js prebuilt package.

    Returns a (version, url)-tuple.
    """
    github_api = 'https://api.github.com'
    endpoint = 'repos/mozilla/pdf.js/releases/latest'
    request = urllib.request.Request(f'{github_api}/{endpoint}')

    if gh_token is not None:
        # Without token will work as well, but has a strict rate limit, so we need to
        # use the token on CI.
        request.add_header('Authorization', f'token {gh_token}')
    elif 'CI' in os.environ:
        raise Exception("No GitHub token given on CI")

    with urllib.request.urlopen(request) as fp:
        data = json.loads(fp.read().decode('utf-8'))

    asset = find_pdfjs_asset(data["assets"], legacy=legacy)

    download_url = asset['browser_download_url']
    version_name = data['name']
    return (version_name, download_url)


def update_pdfjs(target_version=None, legacy=False, gh_token=None):
    """Download and extract the latest pdf.js version.

    If target_version is not None, download the given version instead.

    Args:
        target_version: None or version string ('x.y.z')
        legacy: Whether to download the legacy build for 83-based.
        gh_token: GitHub token to use for the API. Optional except on CI.
    """
    if target_version is None:
        version, url = get_latest_pdfjs_url(gh_token, legacy=legacy)
    else:
        # We need target_version as x.y.z, without the 'v' prefix, though the
        # user might give it on the command line
        if target_version.startswith('v'):
            target_version = target_version[1:]
        # version should have the prefix to be consistent with the return value
        # of get_latest_pdfjs_url()
        version = 'v' + target_version
        suffix = "-legacy" if legacy else ""
        url = ('https://github.com/mozilla/pdf.js/releases/download/'
               f'{version}/pdfjs-{target_version}{suffix}-dist.zip')

    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', '..'))
    target_path = os.path.join('qutebrowser', '3rdparty', 'pdfjs')
    print(f"=> Downloading pdf.js {version}{' (legacy)' if legacy else ''}")
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
    shutil.unpack_archive(archive_path, target_path, 'zip')
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


def update_ace():
    """Update ACE.

    See https://ace.c9.io/ and https://github.com/ajaxorg/ace-builds/
    """
    print("Updating ACE...")
    url = 'https://raw.githubusercontent.com/ajaxorg/ace-builds/master/src/ace.js'
    target_path = os.path.join('tests', 'end2end', 'data', 'hints', 'ace',
                               'ace.js')
    urllib.request.urlretrieve(url, target_path)
    urllib.request.urlcleanup()


def test_dicts():
    """Test available dictionaries."""
    configdata.init()
    for lang in dictcli.available_languages():
        print('Testing dictionary {}... '.format(lang.code), end='')
        lang_url = urllib.parse.urljoin(dictcli.API_URL, lang.remote_filename)
        request = urllib.request.Request(lang_url, method='HEAD')
        with urllib.request.urlopen(request) as response:
            if response.status == 200:
                print('OK')
            else:
                print('ERROR: {}'.format(response.status))


def run(nsis=False, ace=False, pdfjs=True, legacy_pdfjs=False, fancy_dmg=False,
        pdfjs_version=None, dicts=False, gh_token=None):
    """Update components based on the given arguments."""
    if nsis:
        download_nsis_plugins()
    if pdfjs:
        update_pdfjs(pdfjs_version, legacy=legacy_pdfjs, gh_token=gh_token)
    if ace:
        update_ace()
    if fancy_dmg:
        update_dmg_makefile()
    if dicts:
        test_dicts()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nsis', '-n', help='Download NSIS plugins.',
                        required=False, action='store_true')
    parser.add_argument(
        '--pdfjs', '-p',
        help='Specify pdfjs version. If not given, '
        'the latest version is used.',
        required=False, metavar='VERSION')
    parser.add_argument("--legacy-pdfjs",
                        help="Use legacy PDF.js build (for 83-based)",
                        action='store_true')
    parser.add_argument('--fancy-dmg', help="Update fancy-dmg Makefile",
                        action='store_true')
    parser.add_argument(
        '--dicts', '-d',
        help='Test whether all available dictionaries '
        'can be reached at the remote repository.',
        required=False, action='store_true')
    parser.add_argument(
        '--gh-token', help="GitHub token to use.", nargs='?')
    args = parser.parse_args()
    run(nsis=False, ace=True, pdfjs=True, fancy_dmg=args.fancy_dmg,
        pdfjs_version=args.pdfjs, legacy_pdfjs=args.legacy_pdfjs,
        dicts=args.dicts, gh_token=args.gh_token)


if __name__ == '__main__':
    main()
