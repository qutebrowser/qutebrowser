#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""Get qutebrowser crash information and stacktraces from coredumpctl."""

import os
import os.path
import sys
import argparse
import subprocess
import tempfile
import dataclasses

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils


@dataclasses.dataclass
class Line:

    """A line in "coredumpctl list"."""

    time: str
    pid: int
    uid: int
    gid: int
    sig: int
    present: bool
    exe: str


def _convert_present(data):
    """Convert " "/"*" to True/False for parse_coredumpctl_line."""
    if data == '*':
        return True
    elif data == ' ':
        return False
    else:
        raise ValueError(data)


def parse_coredumpctl_line(line):
    """Parse a given string coming from coredumpctl and return a Line object.

    Example input:
        Mon 2015-09-28 23:22:24 CEST  10606  1000  1000  11 /usr/bin/python3.4
    """
    fields = {
        'time': (0, 28, str),
        'pid': (29, 35, int),
        'uid': (36, 41, int),
        'gid': (42, 47, int),
        'sig': (48, 51, int),
        'present': (52, 53, _convert_present),
        'exe': (54, None, str),
    }

    data = {}
    for name, (start, end, converter) in fields.items():
        data[name] = converter(line[start:end])
    return Line(**data)


def get_info(pid):
    """Get and parse "coredumpctl info" output for the given PID."""
    data = {}
    output = subprocess.run(['coredumpctl', 'info', str(pid)], check=True,
                            stdout=subprocess.PIPE).stdout
    output = output.decode('utf-8')
    for line in output.split('\n'):
        if not line.strip():
            continue
        try:
            key, value = line.split(':', maxsplit=1)
        except ValueError:
            # systemd stack output
            continue
        data[key.strip()] = value.strip()
    return data


def is_qutebrowser_dump(parsed):
    """Check if the given Line is a qutebrowser dump."""
    basename = os.path.basename(parsed.exe)
    if basename == 'python' or basename.startswith('python3'):
        info = get_info(parsed.pid)
        try:
            cmdline = info['Command Line']
        except KeyError:
            return True
        else:
            return '-m qutebrowser' in cmdline
    else:
        return basename == 'qutebrowser'


def dump_infos_gdb(parsed):
    """Dump all needed infos for the given crash using gdb."""
    with tempfile.TemporaryDirectory() as tempdir:
        coredump = os.path.join(tempdir, 'dump')
        subprocess.run(['coredumpctl', 'dump', '-o', coredump,
                        str(parsed.pid)], check=True)
        subprocess.run(['gdb', parsed.exe, coredump,
                        '-ex', 'info threads',
                        '-ex', 'thread apply all bt full',
                        '-ex', 'quit'], check=True)


def dump_infos(parsed):
    """Dump all possible infos for the given crash."""
    if not parsed.present:
        info = get_info(parsed.pid)
        print("{}: Signal {} with no coredump: {}".format(
            parsed.time, info.get('Signal', None),
            info.get('Command Line', None)))
    else:
        print('\n\n\n')
        utils.print_title('{} - {}'.format(parsed.time, parsed.pid))
        sys.stdout.flush()
        dump_infos_gdb(parsed)


def check_prerequisites():
    """Check if coredumpctl/gdb are installed."""
    for binary in ['coredumpctl', 'gdb']:
        try:
            subprocess.run([binary, '--version'], check=True)
        except FileNotFoundError:
            print("{} is needed to run this script!".format(binary),
                  file=sys.stderr)
            sys.exit(1)


def main():
    check_prerequisites()

    parser = argparse.ArgumentParser()
    parser.add_argument('--all', help="Also list crashes without coredumps.",
                        action='store_true')
    args = parser.parse_args()

    coredumps = subprocess.run(['coredumpctl', 'list'], check=True,
                               stdout=subprocess.PIPE).stdout
    lines = coredumps.decode('utf-8').split('\n')
    for line in lines[1:]:
        if not line.strip():
            continue
        parsed = parse_coredumpctl_line(line)
        if not parsed.present and not args.all:
            continue
        if is_qutebrowser_dump(parsed):
            dump_infos(parsed)


if __name__ == '__main__':
    main()
