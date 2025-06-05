#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""Generate Dockerfiles for qutebrowser's CI."""

import sys
import argparse

import jinja2


CONFIGS = {
    'archlinux-webengine': {'unstable': False, 'qt6': False},
    'archlinux-webengine-qt6': {'unstable': False, 'qt6': True},
    'archlinux-webengine-unstable': {'unstable': True, 'qt6': False},
    'archlinux-webengine-unstable-qt6': {'unstable': True, 'qt6': True},
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
