#!/usr/bin/env python2
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

# pylint: skip-file

"""Run tests on Travis CI based on environment variables.

Note this file is written in python2 as this is more readily available on the
CI machines.
"""

from __future__ import print_function

import os
import sys
import subprocess


testenv = os.environ['TESTENV']


if 'TRAVIS' not in os.environ:
    def env(key):
        return os.environ.get(key, None)
    print("Unknown environment! (CI {}, APPVEYOR {}, TRAVIS {}, "
          "TRAVIS_OS_NAME {})".format(env('CI'), env('APPVEYOR'),
                                      env('TRAVIS'), env('TRAVIS_OS_NAME')),
          file=sys.stderr)
    sys.exit(1)


travis_os = os.environ['TRAVIS_OS_NAME']

if travis_os == 'linux' and testenv == 'py35':
    raise Exception("Can't run py35 on Linux")
elif travis_os == 'osx' and testenv == 'py34':
    raise Exception("Can't run py34 on OS X")

if testenv == 'eslint':
    subprocess.check_call(['eslint', 'qutebrowser'])
else:
    cmdline = ['tox', '-e', testenv, '--', '-p', 'no:sugar', 'tests']
    subprocess.check_call(cmdline)
