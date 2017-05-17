#!/usr/bin/env python2
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Install needed prerequisites on the AppVeyor.

Note this file is written in python2 as this is more readily available on the
CI machines.
"""

from __future__ import print_function

import subprocess


def pip_install(pkg):
    subprocess.check_call([r'C:\Python34\python', '-m', 'pip', 'install', '-U',
                           pkg])


print("Installing tox")
pip_install('pip')
pip_install(r'-rmisc\requirements\requirements-tox.txt')
