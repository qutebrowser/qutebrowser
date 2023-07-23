#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
