"""Profile qutebrowser."""

import sys
import cProfile
import os.path
from os import getcwd
from tempfile import mkdtemp
from subprocess import call
from shutil import rmtree

sys.path.insert(0, getcwd())

from qutebrowser.app import QuteBrowser  # pylint: disable=unused-import

tempdir = mkdtemp()

if '--keep' in sys.argv:
    sys.argv.remove('--keep')
    profilefile = os.path.join(getcwd(), 'profile')
else:
    profilefile = os.path.join(tempdir, 'profile')
callgraphfile = os.path.join(tempdir, 'callgraph')

profiler = cProfile.Profile()
profiler.run('app = QuteBrowser(); app.exec_()')
profiler.dump_stats(profilefile)

call(['pyprof2calltree', '-k', '-i', profilefile, '-o', callgraphfile])
rmtree(tempdir)
