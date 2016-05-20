#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Get qutebrowser crash information and stacktraces from coredumpctl."""

import os
import sys
import argparse
import subprocess
import collections
import os.path
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

from scripts import utils


Line = collections.namedtuple('Line', 'time, pid, uid, gid, sig, present, exe')


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
    output = subprocess.check_output(['coredumpctl', 'info', str(pid)])
    output = output.decode('utf-8')
    for line in output.split('\n'):
        if not line.strip():
            continue
        key, value = line.split(':', maxsplit=1)
        data[key.strip()] = value.strip()
    return data


def is_qutebrowser_dump(parsed):
    """Check if the given Line is a qutebrowser dump."""
    basename = os.path.basename(parsed.exe)
    if basename in ['python', 'python3', 'python3.4', 'python3.5']:
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
        subprocess.check_call(['coredumpctl', 'dump', '-o', coredump,
                               str(parsed.pid)])
        subprocess.check_call(['gdb', parsed.exe, coredump,
                               '-ex', 'info threads',
                               '-ex', 'thread apply all bt full',
                               '-ex', 'quit'])


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
            subprocess.check_call([binary, '--version'])
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

    coredumps = subprocess.check_output(['coredumpctl', 'list'])
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
