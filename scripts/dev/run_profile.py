#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Profile qutebrowser."""

import sys
import cProfile
import os.path
import os
import tempfile
import subprocess
import shutil
import argparse
import shlex

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

import qutebrowser.qutebrowser


def parse_args():
    """Parse commandline arguments.

    Return:
        A (namespace, remaining_args) tuple from argparse.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile-tool', metavar='TOOL',
                        action='store', choices=['kcachegrind', 'snakeviz',
                                                 'gprof2dot', 'none'],
                        default='snakeviz',
                        help="The tool to use to view the profiling data")
    parser.add_argument('--profile-file', metavar='FILE', action='store',
                        help="The filename to use with --profile-tool=none")
    return parser.parse_known_args()


def main():
    args, remaining = parse_args()
    tempdir = tempfile.mkdtemp()

    if args.profile_tool == 'none':
        profilefile = os.path.join(os.getcwd(), args.profile_file)
    else:
        profilefile = os.path.join(tempdir, 'profile')

    sys.argv = [sys.argv[0]] + remaining

    profiler = cProfile.Profile()
    profiler.runcall(qutebrowser.qutebrowser.main)
    profiler.dump_stats(profilefile)

    if args.profile_tool == 'none':
        pass
    elif args.profile_tool == 'gprof2dot':
        # yep, shell=True. I know what I'm doing.
        subprocess.call('gprof2dot -f pstats {} | dot -Tpng | feh -F -'.format(
                        shlex.quote(profilefile)), shell=True)
    elif args.profile_tool == 'kcachegrind':
        callgraphfile = os.path.join(tempdir, 'callgraph')
        subprocess.call(['pyprof2calltree', '-k', '-i', profilefile,
                         '-o', callgraphfile])
    elif args.profile_tool == 'snakeviz':
        subprocess.call(['snakeviz', profilefile])

    shutil.rmtree(tempdir)


if __name__ == '__main__':
    main()
