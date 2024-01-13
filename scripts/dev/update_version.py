#!/usr/bin/env python3

# SPDX-FileCopyrightText: Andy Mender <andymenderunix@gmail.com>
# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""Update version numbers using bump2version."""

import re
import sys
import argparse
import os.path
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils


class Error(Exception):
    """Base class for exceptions in this module."""


def verify_branch(version_leap):
    """Check that we're on the correct git branch."""
    proc = subprocess.run(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        check=True, capture_output=True, text=True)
    branch = proc.stdout.strip()

    if (
        version_leap == 'patch' and not re.fullmatch(r'v\d+\.\d+\.x', branch) or
        version_leap != 'patch' and branch != 'main'
    ):
        raise Error(f"Invalid branch for {version_leap} release: {branch}")


def bump_version(version_leap="patch"):
    """Update qutebrowser release version.

    Args:
        version_leap: define the jump between versions
        ("major", "minor", "patch")
    """
    subprocess.run([sys.executable, '-m', 'bumpversion', version_leap],
                   check=True)


def show_commit():
    """Show the latest git commit."""
    git_args = ['git', 'show']
    if utils.ON_CI:
        git_args.append("--color")
    subprocess.run(git_args, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update release version.")
    parser.add_argument('bump', action="store",
                        choices=["major", "minor", "patch"],
                        help="Update release version")
    parser.add_argument('--commands', action="store_true",
                        help="Only show commands to run post-release.")
    args = parser.parse_args()

    utils.change_cwd()

    if not args.commands:
        verify_branch(args.bump)
        bump_version(args.bump)
        show_commit()

    import qutebrowser
    version = qutebrowser.__version__
    version_x = '.'.join([str(p) for p in qutebrowser.__version_info__[:-1]] +
                         ['x'])

    if utils.ON_CI:
        output_file = os.environ["GITHUB_OUTPUT"]
        with open(output_file, "w", encoding="ascii") as f:
            f.write(f"version={version}\n")
            f.write(f"version_x={version_x}\n")

        print(f"Outputs for {version} written to GitHub Actions output file")
    else:
        print("Run the following commands to create a new release:")
        print("* git push origin; git push origin v{v}".format(v=version))
        if args.bump == 'patch':
            print("* git checkout main && git cherry-pick -x v{v} && "
                "git push origin".format(v=version))
        else:
            print("* git branch v{x} v{v} && git push --set-upstream origin v{x}"
                .format(v=version, x=version_x))
        print("* Create new release via GitHub (required to upload release "
            "artifacts)")
        print("* Linux: git fetch && git checkout v{v} && "
            "tox -e build-release -- --upload"
            .format(v=version))
        print("* Windows: git fetch; git checkout v{v}; "
            "py -3.X -m tox -e build-release -- --upload"
            .format(v=version))
        print("* macOS: git fetch && git checkout v{v} && "
            "tox -e build-release -- --upload"
            .format(v=version))
