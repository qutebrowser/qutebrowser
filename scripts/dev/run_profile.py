#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                os.pardir))

import qutebrowser.qutebrowser  # pylint: disable=unused-import

tempdir = tempfile.mkdtemp()

if '--profile-keep' in sys.argv:
    sys.argv.remove('--profile-keep')
    profilefile = os.path.join(os.getcwd(), 'profile')
else:
    profilefile = os.path.join(tempdir, 'profile')

if '--profile-noconv' in sys.argv:
    sys.argv.remove('--profile-noconv')
    noconv = True
else:
    noconv = False

if '--profile-dot' in sys.argv:
    sys.argv.remove('--profile-dot')
    dot = True
else:
    dot = False

callgraphfile = os.path.join(tempdir, 'callgraph')
profiler = cProfile.Profile()
profiler.run('qutebrowser.qutebrowser.main()')
profiler.dump_stats(profilefile)

if not noconv:
    if dot:
        subprocess.call('gprof2dot -f pstats profile | dot -Tpng | feh -F -',
                        shell=True)  # yep, shell=True. I know what I'm doing.
    else:
        subprocess.call(['pyprof2calltree', '-k', '-i', profilefile,
                        '-o', callgraphfile])
shutil.rmtree(tempdir)
