#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Change a description of a GitHub release."""

import sys
import argparse
import os.path

import github3
import github3.exceptions


class Error(Exception):

    """Raised for errors in this script."""


def read_github_token():
    """Read the GitHub API token from disk."""
    token_file = os.path.join(os.path.expanduser('~'), '.gh_token')
    with open(token_file, encoding='ascii') as f:
        token = f.read().strip()
    return token


def find_release(repo, tag):
    """Find the release for the given repo/tag."""
    release = None  # to satisfy pylint
    for release in repo.releases():
        if release.tag_name == tag:
            break
    else:
        raise Error("No release found for {!r}!".format(tag))
    return release


def change_release_description(release, filename, description):
    """Change a release description to the given new one."""
    assets = [asset for asset in release.assets() if asset.name == filename]
    if not assets:
        raise Error(f"No assets found for {filename}")
    if len(assets) > 1:
        raise Error(f"Multiple assets found for {filename}: {assets}")

    asset = assets[0]
    asset.edit(filename, description)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('tag')
    parser.add_argument('filename')
    parser.add_argument('description')
    return parser.parse_args()


def main():
    args = parse_args()

    token = read_github_token()
    gh = github3.login(token=token)
    repo = gh.repository('qutebrowser', 'qutebrowser')

    try:
        release = find_release(repo, args.tag)
        change_release_description(release, args.filename, args.description)
    except Error as e:
        sys.exit(str(e))


if __name__ == '__main__':
    main()
