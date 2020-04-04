#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Andy Mender <andymenderunix@gmail.com>
# Copyright 2019-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Update version numbers using bump2version."""

import sys
import argparse
import os.path
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils


def bump_version(version_leap="patch"):
    """Update qutebrowser release version.

    Args:
        version_leap: define the jump between versions
        ("major", "minor", "patch")
    """
    subprocess.run([sys.executable, '-m', 'bumpversion', version_leap],
                   check=True)


def show_commit():
    subprocess.run(['git', 'show'], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update release version.")
    parser.add_argument('bump', action="store",
                        choices=["major", "minor", "patch"],
                        help="Update release version")
    args = parser.parse_args()

    utils.change_cwd()
    bump_version(args.bump)
    show_commit()

    import qutebrowser
    version = qutebrowser.__version__
    x_version = '.'.join([str(p) for p in qutebrowser.__version_info__[:-1]] +
                         ['x'])

    print("Run the following commands to create a new release:")
    print("* git push origin; git push origin v{v}".format(v=version))
    if args.bump == 'patch':
        print("* git checkout master && git cherry-pick v{v} && "
              "git push origin".format(v=version))
    else:
        print("* git branch v{x} v{v} && git push --set-upstream origin v{x}"
              .format(v=version, x=x_version))
    print("* Create new release via GitHub (required to upload release "
          "artifacts)")
    print("* Linux: git fetch && git checkout v{v} && "
          "./.venv/bin/python3 scripts/dev/build_release.py --upload"
          .format(v=version))
    print("* Windows: git fetch; git checkout v{v}; "
          "py -3 scripts\\dev\\build_release.py --asciidoc "
          "C:\\Python27\\python "
          "$env:userprofile\\bin\\asciidoc-8.6.10\\asciidoc.py --upload"
          .format(v=version))
    print("* macOS: git fetch && git checkout v{v} && "
          "python3 scripts/dev/build_release.py --upload"
          .format(v=version))

    print("* On server:")
    print("  - bash download_release.sh {v}"
          .format(v=version))
    print("  - git pull github master && sudo python3 "
          "scripts/asciidoc2html.py --website /srv/http/qutebrowser")
