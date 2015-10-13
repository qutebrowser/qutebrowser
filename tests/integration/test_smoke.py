# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test which simply runs qutebrowser to check if it starts properly."""


import sys
import os.path
import subprocess


def test_smoke():
    if hasattr(sys, 'frozen'):
        argv = [os.path.join(os.path.dirname(sys.executable), 'qutebrowser')]
    else:
        argv = [sys.executable, '-m', 'qutebrowser']
    argv += ['--debug', '--no-err-windows', '--nowindow', '--temp-basedir',
             'about:blank', ':later 500 quit']
    subprocess.check_call(argv)
