#!/usr/bin/env python3
# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
                                                 'gprof2dot', 'tuna', 'none'],
                        default='snakeviz',
                        help="The tool to use to view the profiling data")
    parser.add_argument('--profile-file', metavar='FILE', action='store',
                        default="profile_data",
                        help="The filename to use with --profile-tool=none")
    parser.add_argument('--profile-test', action='store_true',
                        help="Run pytest instead of qutebrowser")
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

    if args.profile_test:
        import pytest
        profiler.runcall(pytest.main)
    else:
        profiler.runcall(qutebrowser.qutebrowser.main)

    # If we have an exception after here, we don't want the qutebrowser
    # exception hook to take over.
    sys.excepthook = sys.__excepthook__
    profiler.dump_stats(profilefile)

    if args.profile_tool == 'none':
        print("Profile data written to {}".format(profilefile))
    elif args.profile_tool == 'gprof2dot':
        # yep, shell=True. I know what I'm doing.
        subprocess.run(
            'gprof2dot -f pstats {} | dot -Tpng | feh -F -'.format(
                shlex.quote(profilefile)), shell=True, check=True)
    elif args.profile_tool == 'kcachegrind':
        callgraphfile = os.path.join(tempdir, 'callgraph')
        subprocess.run(['pyprof2calltree', '-k', '-i', profilefile,
                        '-o', callgraphfile], check=True)
    elif args.profile_tool == 'snakeviz':
        subprocess.run(['snakeviz', profilefile], check=True)
    elif args.profile_tool == 'tuna':
        subprocess.run(['tuna', profilefile], check=True)

    shutil.rmtree(tempdir)


if __name__ == '__main__':
    main()
