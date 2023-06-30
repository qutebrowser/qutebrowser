#!/usr/bin/env python3
# Copyright 2019-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Generate Dockerfiles for qutebrowser's CI."""

import sys
import argparse

import jinja2


CONFIGS = {
    'archlinux-webkit': {'webengine': False, 'unstable': False, 'qt6': False},
    'archlinux-webengine': {'webengine': True, 'unstable': False, 'qt6': False},
    'archlinux-webengine-qt6': {'webengine': True, 'unstable': False, 'qt6': True},
    'archlinux-webengine-unstable': {'webengine': True, 'unstable': True, 'qt6': False},
    'archlinux-webengine-unstable-qt6': {'webengine': True, 'unstable': True, 'qt6': True},
}


def main():
    with open('Dockerfile.j2') as f:
        template = jinja2.Template(f.read(), trim_blocks=True, lstrip_blocks=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("config", choices=CONFIGS)
    args = parser.parse_args()

    config = CONFIGS[args.config]

    with open('Dockerfile', 'w') as f:
        f.write(template.render(**config))
        f.write('\n')


if __name__ == '__main__':
    main()
